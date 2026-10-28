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

    def __init__(self, process: subprocess.Popen, group: bool = False):
        self._process = process
        self._group = group

    @property
    def running(self) -> bool:
        return self._process.poll() is None

    def terminate(self) -> None:
        if not self.running:
            return
        if self._group and os.name != 'nt':
            try:
                os.killpg(self._process.pid, signal.SIGTERM)
                return
            except (ProcessLookupError, PermissionError, OSError):
                pass
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
              on_exit: Optional[ExitListener] = None,
              on_error: Optional[OutputListener] = None,
              group: bool = False) -> RunningCommand:
        argv = list(argv)
        log.info('start %s', argv)
        options: dict = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.PIPE,
                         'text': True, 'errors': 'replace', 'bufsize': 1}
        options['stderr'] = subprocess.PIPE if on_error else subprocess.STDOUT
        if group and os.name != 'nt':
            options['start_new_session'] = True
        elif group and os.name == 'nt':
            options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            process = subprocess.Popen(argv, **options)
        except FileNotFoundError:
            self._in_background(self._report_missing, argv[0], on_output, on_exit)
            return _FinishedCommand()

        if on_error:
            self._in_background(self._pump_split, process, on_output, on_error, on_exit)
        else:
            self._in_background(self._pump, process, on_output, on_exit)
        return _SubprocessCommand(process, group)

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
    def _pump_split(process: subprocess.Popen,
                    on_output: Optional[OutputListener],
                    on_error: Optional[OutputListener],
                    on_exit: Optional[ExitListener]) -> None:
        threads = [
            threading.Thread(target=SubprocessCommandRunner._read, args=(process.stdout, on_output), daemon=True),
            threading.Thread(target=SubprocessCommandRunner._read, args=(process.stderr, on_error), daemon=True),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        code = process.wait()
        if on_exit:
            on_exit(code)

    @staticmethod
    def _read(stream, callback: Optional[OutputListener]) -> None:
        if stream is None:
            return
        for line in stream:
            if callback:
                callback(line)
        stream.close()

    @staticmethod
    def _report_missing(executable: str,
                        on_output: Optional[OutputListener],
                        on_exit: Optional[ExitListener]) -> None:
        if on_output:
            on_output(_missing_message(executable))
        if on_exit:
            on_exit(MISSING_COMMAND_CODE)
