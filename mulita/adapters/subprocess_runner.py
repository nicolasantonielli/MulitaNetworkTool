from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
from typing import Optional, Sequence

from mulita.core.models import MISSING_COMMAND_CODE, TIMEOUT_CODE, CommandResult
from mulita.presentation.i18n import tr
from mulita.core.ports import (CommandRunner, ExitListener, OutputListener,
                               RunningCommand)

log = logging.getLogger(__name__)


def _missing_message(executable: str) -> str:
    return tr('missingCommand', name=executable) + '\n'


def _as_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode(errors='replace')
    return value or ''


class _SubprocessCommand(RunningCommand):

    def __init__(self, process: subprocess.Popen):
        self._process = process

    @property
    def running(self) -> bool:
        return self._process.poll() is None

    def terminate(self) -> None:
        if self.running:
            self._process.terminate()

    def interrupt(self) -> None:
        if not self.running:
            return
        if os.name == 'nt':
            self._process.terminate()
        else:
            self._process.send_signal(signal.SIGINT)


class _FinishedCommand(RunningCommand):

    @property
    def running(self) -> bool:
        return False

    def terminate(self) -> None:
        pass

    def interrupt(self) -> None:
        pass


class SubprocessCommandRunner(CommandRunner):

    def run(self, argv: Sequence[str], timeout: float | None = None,
            input_text: str | None = None) -> CommandResult:
        argv = list(argv)
        log.info('run %s', argv)
        options = {'input': input_text} if input_text is not None else {'stdin': subprocess.DEVNULL}
        try:
            completed = subprocess.run(
                argv, capture_output=True, text=True, errors='replace',
                timeout=timeout, **options)
        except FileNotFoundError:
            return CommandResult(MISSING_COMMAND_CODE, '', _missing_message(argv[0]))
        except subprocess.TimeoutExpired as exc:
            return CommandResult(TIMEOUT_CODE, _as_text(exc.stdout), 'Tiempo de espera agotado')
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)

    def start(self, argv: Sequence[str],
              on_output: Optional[OutputListener] = None,
              on_exit: Optional[ExitListener] = None) -> RunningCommand:
        argv = list(argv)
        log.info('start %s', argv)
        try:
            process = subprocess.Popen(
                argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, errors='replace', bufsize=1)
        except FileNotFoundError:
            self._in_background(self._report_missing, argv[0], on_output, on_exit)
            return _FinishedCommand()

        self._in_background(self._pump, process, on_output, on_exit)
        return _SubprocessCommand(process)

    @staticmethod
    def _in_background(target, *args) -> None:
        threading.Thread(target=target, args=args, daemon=True).start()

    @staticmethod
    def _pump(process: subprocess.Popen,
              on_output: Optional[OutputListener],
              on_exit: Optional[ExitListener]) -> None:
        for line in process.stdout:
            if on_output:
                on_output(line)
        process.stdout.close()
        code = process.wait()
        if on_exit:
            on_exit(code)

    @staticmethod
    def _report_missing(executable: str,
                        on_output: Optional[OutputListener],
                        on_exit: Optional[ExitListener]) -> None:
        if on_output:
            on_output(_missing_message(executable))
        if on_exit:
            on_exit(MISSING_COMMAND_CODE)
