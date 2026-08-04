import argparse
import ctypes
import json
import os
import platform
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

if TYPE_CHECKING:
    # The context and settings modules form a circular dependency. The settings module
    # is only used for a type annotation in this module, so we let the type checkers
    # deal with the circular dependency, while during normal runtime it will not exist.
    from caerbannog.settings import Settings

if platform.system() == "Linux":
    import grp
    import pwd

from caerbannog import var_loader
from caerbannog.elevation_type import ElevationType
from caerbannog.error import CaerbannogError
from caerbannog.roles.role_context import RoleContext

_context: dict[str, Any] = {
    "root": os.getcwd(),
    "current_role": None,
    "role_vars": {},
    "elevation": str(ElevationType.NONE),
}
_role_context = None
_settings = None

_should_modify = True
_should_confirm = False


def _load_vars():
    _context["vars"] = var_loader.load_all()


# https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid
_FOLDERID_DOCUMENTS = UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7")


def _find_documents_dir(home_dir: str) -> str:
    if platform.system() == "Windows":
        # This is not necessarily `~/Documents`: it may be relocated, and the
        # shell is the only authority on where it went.
        return _known_folder_path(_FOLDERID_DOCUMENTS)

    # An exported variable wins, as it does for the base directories, but
    # xdg-user-dirs normally only writes `user-dirs.dirs`, so that file is the
    # authority here. Fall back to the conventional location if it says nothing.
    return (
        os.environ.get("XDG_DOCUMENTS_DIR")
        or _xdg_user_dir("DOCUMENTS", home_dir)
        or os.path.join(home_dir, "Documents")
    )


# https://www.freedesktop.org/wiki/Software/xdg-user-dirs/
def _xdg_user_dir(name: str, home_dir: str) -> str | None:
    # `user-dirs.dirs` is shell syntax, meant to be sourced:
    #     XDG_DOCUMENTS_DIR="$HOME/Documents"
    # Paths are absolute, or relative to `$HOME`. A later assignment overrides
    # an earlier one, as it would when sourced.
    config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home_dir, ".config")

    try:
        with open(
            os.path.join(config_home, "user-dirs.dirs"), encoding="utf-8"
        ) as file:
            lines = file.readlines()
    except OSError:
        return None

    found = None
    for line in lines:
        key, _, value = line.partition("=")
        if key.strip() != f"XDG_{name}_DIR":
            continue

        value = value.strip().strip("\"'")
        if value.startswith("$HOME"):
            value = home_dir + value[len("$HOME") :]
        elif not os.path.isabs(value):
            value = os.path.join(home_dir, value)

        found = value or None

    return found


def _known_folder_path(folder_id: UUID) -> str:
    guid = (ctypes.c_byte * 16).from_buffer_copy(folder_id.bytes_le)
    buffer = ctypes.c_wchar_p()

    result = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(guid), 0, None, ctypes.byref(buffer)
    )
    try:
        if result != 0 or buffer.value is None:
            raise CaerbannogError(
                f"could not resolve known folder {folder_id}: "
                f"SHGetKnownFolderPath returned 0x{result & 0xFFFFFFFF:08X}"
            )
        return buffer.value
    finally:
        # Freeing a null pointer is a no-op, so this is also safe on failure.
        ctypes.windll.ole32.CoTaskMemFree(buffer)


def _load_host():
    # Captured before elevation, so that these variables keep describing the
    # invoking user rather than root once privileges are raised.
    user: dict[str, Any] = {}
    if platform.system() == "Linux":
        user["username"] = pwd.getpwuid(os.getuid()).pw_name
        user["groupname"] = grp.getgrgid(os.getgid()).gr_name
        user["uid"] = os.getuid()
        user["gid"] = os.getgid()
        user["home_dir"] = os.path.expanduser(f"~{user['username']}")
    else:
        user["username"] = os.getlogin()
        user["home_dir"] = os.path.expanduser("~")

    user["documents_dir"] = _find_documents_dir(user["home_dir"])

    _context["env"] = {k: v for (k, v) in os.environ.items()}

    _context["host"] = {"os": os.name, "system": platform.system(), "user": user}


def init(args: argparse.Namespace):
    def try_read(key):
        if hasattr(args, key):
            return getattr(args, key)
        return None

    global _should_modify
    global _should_confirm
    global _context

    _should_modify = not try_read("dry_run")
    _should_confirm = try_read("confirm")

    serialized_context = try_read("context")
    if serialized_context is not None:
        _context = json.loads(serialized_context)

    else:
        _context["target"] = try_read("target")

        if platform.system() == "Windows":
            if try_read("elevate"):
                raise CaerbannogError("Elevation is not supported on Windows")
            else:
                _context["elevation"] = str(ElevationType.NONE)
        else:
            if try_read("elevate"):
                _context["elevation"] = str(ElevationType.ELEVATED)
            else:
                _context["elevation"] = str(ElevationType.JUST_IN_TIME)

        _load_host()
        _load_vars()


def serialize() -> str:
    return json.dumps(_context)


def context():
    return _context


def elevation() -> "ElevationType":
    return ElevationType(_context["elevation"])


def root() -> str:
    return _context["root"]


def user_home_dir() -> str:
    return _context["host"]["user"]["home_dir"]


def user_documents_dir() -> str:
    return _context["host"]["user"]["documents_dir"]


def username() -> str:
    return _context["host"]["user"]["username"]


def groupname() -> str:
    return _context["host"]["user"]["groupname"]


def vars():
    return _context["vars"]


T = TypeVar("T")


def get_var(name: str, default: T | None = None) -> Any | T:
    """
    Retrieves a variable using a dot-separated path. Returns `None` if the
    variable (or any part of its path) is not defined. Use the `default`
    parameter to specify a different default value.
    """
    path = name.split(".")
    current = _context["vars"]
    for part in path:
        if part not in current:
            return default
        current = current[part]

    return current


def env(variable=None):
    if variable is not None:
        return _context["env"][variable]

    return _context["env"]


def current_role() -> str:
    return _context["current_role"]


def current_role_dir() -> str:
    return role_dir(current_role())


def role_dir(role: str) -> str:
    return os.path.join(root(), "roles", role)


def resolve_path(*paths_to_resolve: str) -> str:
    return os.path.join(current_role_dir(), *paths_to_resolve)


def should_modify():
    """
    Returns `False` if `--dry-run` is specified, `True` otherwise.
    """
    return _should_modify


def should_confirm():
    """
    Returns `True` if `--confirm` is specified, `False` otherwise.
    """
    return _should_confirm


def role_vars():
    """
    Returns a collection of variables that can be written to during execution
    of the current role. After the role has finished executing, the variables
    are cleared.
    """
    return _context["role_vars"]


def system():
    return _context["host"]["system"]


def settings() -> "Settings":
    if _settings is None:
        raise CaerbannogError("Settings are not available yet")
    return _settings


def role_context() -> "RoleContext":
    if _role_context is None:
        raise CaerbannogError("No role is currently executing")

    return _role_context


@contextmanager
def role(name, log):
    global _role_context
    try:
        _role_context = RoleContext(log)
        _context["role_vars"] = {}
        _context["current_role"] = name
        yield _role_context
    finally:
        _role_context = None
        _context["role_vars"] = {}
        _context["current_role"] = None


@contextmanager
def dry_run():
    global _should_modify
    backup = _should_modify
    _should_modify = False
    try:
        yield
    finally:
        _should_modify = backup
