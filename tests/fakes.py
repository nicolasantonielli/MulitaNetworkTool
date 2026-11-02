from __future__ import annotations

from typing import Optional, Sequence

from mulita.core.models import CommandResult
from mulita.core.ports import (CommandRunner, ExitListener, OutputListener,
                               RunningCommand)


class FakeCommand(RunningCommand):

    def __init__(self, on_exit: Optional[ExitListener]):
        self._on_exit = on_exit
        self._running = True
        self.signals: list[str] = []

    @property
    def running(self) -> bool:
        return self._running

    def finish(self, code: int = 0) -> None:
        self._running = False
        if self._on_exit:
            self._on_exit(code)

    def terminate(self) -> None:
        self.signals.append('TERM')
        self.finish(-15)

    def interrupt(self) -> None:
        self.signals.append('INT')
        self.finish(0)


class FakeRunner(CommandRunner):

    def __init__(self, results: dict[str, CommandResult] | None = None):
        self.results = results or {}
        self.runs: list[list[str]] = []
        self.inputs: list[str | None] = []
        self.starts: list[list[str]] = []
        self.handles: list[FakeCommand] = []
        self.outputs: list[Optional[OutputListener]] = []
        self.errors: list[Optional[OutputListener]] = []
        self.groups: list[bool] = []

    def run(self, argv: Sequence[str], timeout: float | None = None,
            input_text: str | None = None) -> CommandResult:
        self.runs.append(list(argv))
        self.inputs.append(input_text)
        return self.results.get(argv[0], CommandResult(0, 'ok\n'))

    def start(self, argv: Sequence[str],
              on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None,
              on_error: Optional[OutputListener] = None,
              group: bool = False) -> RunningCommand:
        self.starts.append(list(argv))
        self.outputs.append(on_output)
        self.errors.append(on_error)
        self.groups.append(group)
        handle = FakeCommand(on_exit)
        self.handles.append(handle)
        return handle


class FakeBacklight:
    def available(self):
        return False

    def apply(self, percent):
        pass


class FakeStorage:
    def __init__(self, drives=()):
        self.drives = drives
        self.syncs = 0

    def list_drives(self):
        return tuple(self.drives)

    def folder(self, drive_id):
        from pathlib import Path
        from mulita.core.errors import ValidationError
        from mulita.core.messages import message
        for drive in self.drives:
            if drive.device == drive_id:
                return Path(drive.mountpoint)
        raise ValidationError(message('usbMissing'))

    def sync(self):
        self.syncs += 1
