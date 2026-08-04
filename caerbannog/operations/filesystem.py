# These helpers must resolve paths from the context, never from the live system:
# under `--elevate`, a live lookup would describe root instead of the invoking
# user.

import os

from caerbannog import context
from caerbannog.error import CaerbannogError


def local_app_data(*subpath: str):
    local = context.env().get("LOCALAPPDATA", None)
    if local is None:
        raise CaerbannogError("%LOCALAPPDATA% not found")
    return append_subpath(local, *subpath)


def roaming_app_data(*subpath: str):
    appdata = context.env().get("APPDATA", None)
    if appdata is None:
        raise CaerbannogError("%APPDATA% not found")
    return append_subpath(appdata, *subpath)


def home_dir(*subpath: str):
    return append_subpath(context.user_home_dir(), *subpath)


def documents_dir(*subpath: str):
    return append_subpath(context.user_documents_dir(), *subpath)


def xdg_config_home(*subpath: str):
    dir = context.env().get("XDG_CONFIG_HOME", None)
    if dir is None:
        dir = home_dir(".config")

    return append_subpath(dir, *subpath)


def xdg_data_home(*subpath: str):
    dir = context.env().get("XDG_DATA_HOME", None)
    if dir is None:
        dir = home_dir(".local/share")

    return append_subpath(dir, *subpath)


def xdg_cache_home(*subpath: str):
    dir = context.env().get("XDG_CACHE_HOME", None)
    if dir is None:
        dir = home_dir(".cache")

    return append_subpath(dir, *subpath)


def append_subpath(base: str, *subpath: str):
    if subpath:
        return os.path.join(base, *subpath)
    else:
        return base
