import subprocess

from caerbannog import command
from caerbannog.logging import fmt
from caerbannog.operations import Assertion, Change, DiffLine, Subject, host


class Package(Subject):
    def __init__(self, *ids: str) -> None:
        super().__init__()
        self._names = list(ids)

    def is_installed(self):
        if host.is_arch_linux():
            self.add_assertion(PacmanPackageIsInstalled(set(self._names)))
        elif host.is_windows():
            for name in self._names:
                self.add_assertion(WinGetPackageIsInstalled(name))
        else:
            raise NotImplementedError()

        return self

    def describe(self):
        joined = ", ".join(map(fmt.subject, self._names))
        if len(self._names) > 1:
            return f"packages {joined}"
        return f"package {joined}"


class WinGetPackage(Subject):
    def __init__(self, *ids: str) -> None:
        super().__init__()
        self._ids = list(ids)

    def is_installed(self):
        if not host.is_arch_linux():
            raise NotImplementedError()

        for id in self._ids:
            self.add_assertion(WinGetPackageIsInstalled(id))
        return self

    def describe(self):
        joined = ", ".join(map(fmt.subject, self._ids))
        if len(self._ids) > 1:
            return f"WinGet packages {joined}"
        return f"WinGet package {joined}"


class PacmanPackage(Subject):
    def __init__(self, *names: str) -> None:
        super().__init__()
        self._names = list(names)

    def is_installed(self):
        if not host.is_arch_linux():
            raise NotImplementedError()

        self.add_assertion(PacmanPackageIsInstalled(set(self._names)))
        return self

    def describe(self):
        joined = ", ".join(map(fmt.subject, self._names))
        if len(self._names) > 1:
            return f"Pacman packages {joined}"
        return f"Pacman package {joined}"


class WinGetPackageIsInstalled(Assertion):
    def __init__(self, id: str) -> None:
        descr = "is installed"
        super().__init__(descr)
        self._package_id = id

    def apply(self):
        query = subprocess.run(
            ["winget", "list", "--disable-interactivity", "--id", self._package_id],
            capture_output=True,
        )
        if query.returncode == 0:
            return

        self.register_change(WinGetPackageInstalled(self._package_id))


class PacmanPackageIsInstalled(Assertion):
    _cache: tuple[set[str], dict[str, set[str]]] | None = None

    def __init__(self, names: set[str]) -> None:
        if len(names) > 1:
            descr = "are installed"
        else:
            descr = "is installed"
        super().__init__(descr)
        self._package_names = names

    def apply(self):
        packages, groups = PacmanPackageIsInstalled._load_installed()

        present = packages | groups.keys()
        missing = self._package_names - present

        if len(missing) == 0:
            return

        self.register_change(PacmanPackageInstalled(missing))

    @staticmethod
    def _load_installed() -> tuple[set[str], dict[str, set[str]]]:
        if PacmanPackageIsInstalled._cache is not None:
            return PacmanPackageIsInstalled._cache

        query_packages = subprocess.run(
            ["pacman", "--query", "--quiet"],
            capture_output=True,
            text=True,
            check=True,
        )
        query_groups = subprocess.run(
            ["pacman", "--query", "--groups"],
            capture_output=True,
            text=True,
            check=True,
        )
        packages = set(query_packages.stdout.splitlines())
        groups: dict[str, set[str]] = {}
        for line in query_groups.stdout.splitlines():
            [group, package] = line.split(" ")
            entry = groups.setdefault(group, set())
            entry.add(package)

        PacmanPackageIsInstalled._cache = packages, groups
        return packages, groups


class PacmanPackageInstalled(Change):
    def __init__(self, packages: set[str]):
        self._pachages = packages
        super().__init__("installed", [DiffLine.add(name) for name in packages])

    def execute(self):
        install = subprocess.run(
            command.create_elevated_command(
                "pacman", "--sync", "--noconfirm", *self._pachages
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if install.returncode != 0:
            raise Exception("installation failed", install.stdout)


class WinGetPackageInstalled(Change):
    def __init__(self, name: str):
        self._package_name = name
        super().__init__("installed", [DiffLine.add(name)])

    def execute(self):
        install = subprocess.run(
            [
                "winget",
                "install",
                "--disable-interactivity",
                "--id",
                self._package_name,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if install.returncode != 0:
            raise Exception("installation failed", install.stdout.splitlines())
