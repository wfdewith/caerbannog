import sys
from collections.abc import Iterator
from types import ModuleType

import pytest


@pytest.fixture(scope="function")
def target() -> Iterator[ModuleType]:
    import caerbannog.target

    yield caerbannog.target
    del sys.modules["caerbannog.target"]
