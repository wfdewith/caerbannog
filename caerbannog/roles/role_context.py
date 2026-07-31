from caerbannog import context
from caerbannog.error import CaerbannogError
from caerbannog.logging import LogContext
from caerbannog.operations import Handler, Subject


class RoleContext:
    def __init__(self, log: LogContext) -> None:
        self._handlers: list[Handler] = []
        self._log = log

    def do(self, subjects: list[Subject]):
        for subject in subjects:
            subject.apply(self._log)

    def ensure(self, subjects: list[Subject]):
        with context.dry_run():
            assert_log = self._log.changes_are_errors()
            with assert_log.level():
                assert_log.no_change("assert that")
                for subject in subjects:
                    subject.apply(assert_log)
                    if subject.changed():
                        raise CaerbannogError("assertion failed")

    def add_handler(self, handler: Handler):
        self._handlers.append(handler)

    def remove_handler(self, handler: Handler):
        self._handlers.remove(handler)

    def run_handlers(self):
        for handler in self._handlers:
            handler.apply(self._log)
