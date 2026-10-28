"""Analisis de certificados TLS con testssl.sh."""
from __future__ import annotations

import json
import re
from collections import deque
from datetime import datetime
from typing import Callable

from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from mulita.core.errors import MulitaError
from mulita.core.models import MISSING_COMMAND_CODE
from mulita.core.tls import DEFAULT_MODE, MODES, grouped, summarize
from mulita.presentation.i18n import tr
from mulita.ui.qt.bridge.base import BridgeContext, SessionController


class TlsController(SessionController):
    resultChanged = pyqtSignal()

    def __init__(self, ctx: BridgeContext, clock: Callable[[], str] | None = None):
        super().__init__(ctx, ctx.services.tls)
        self._clock = clock or (lambda: datetime.now().strftime('%Y%m%d-%H%M%S'))
        self._findings: tuple = ()
        self._target = ''
        self._stopping = False
        self._tail: deque[str] = deque(maxlen=6)

    @pyqtProperty(str, constant=True)
    def modesJson(self) -> str:
        return json.dumps({'default': DEFAULT_MODE,
                           'items': [{'id': key, 'title': title} for key, (title, _) in MODES.items()]})

    @pyqtProperty(str, notify=resultChanged)
    def rowsJson(self) -> str:
        return json.dumps(grouped(self._findings))

    @pyqtProperty(str, notify=resultChanged)
    def summaryJson(self) -> str:
        return json.dumps(summarize(self._findings))

    @pyqtProperty(str, notify=resultChanged)
    def target(self) -> str:
        return self._target

    @pyqtProperty(bool, notify=resultChanged)
    def hasResult(self) -> bool:
        return bool(self._findings)

    @pyqtSlot(str, str, result=bool)
    def start(self, target: str, mode: str) -> bool:
        if self._session.is_running:
            return False
        self._reset()
        self._stopping = False

        def starter(**callbacks) -> None:
            self._target = self._session.start(target, mode, **callbacks).label
            self.resultChanged.emit()

        return self._launch(starter)

    @pyqtSlot()
    def stop(self) -> None:
        self._stopping = True
        super().stop()

    @pyqtSlot()
    def save(self) -> None:
        """Guarda el resultado como CSV. El nombre lleva el servidor y la hora."""
        if self._running:
            return
        try:
            name = self._services.tls.save(self._findings, self._filename())
        except MulitaError as exc:
            self._fail(exc)
            return
        self._ctx.notifier.success(tr('cyberTls'), name)

    def _filename(self) -> str:
        slug = re.sub(r'[^A-Za-z0-9._-]+', '-', self._target.rsplit(':', 1)[0]).strip('-._')
        return f'tls-{slug or "servidor"}-{self._clock()}'

    def _reset(self) -> None:
        self._findings = ()
        self._tail.clear()
        self._console.clear()
        self.resultChanged.emit()

    def _output(self, text: str) -> None:
        clean = text.replace('\r', '')
        for line in clean.splitlines():
            if line.strip():
                self._tail.append(line.strip()[:300])
        self._console.append(clean)

    def _finished(self, code: int) -> None:
        self._findings = self._session.findings
        self.resultChanged.emit()
        if self._stopping:
            return
        title = tr('cyberTls')
        if code == MISSING_COMMAND_CODE:
            self._ctx.notifier.error(tr('tlsMissing'), title=title)
        elif not self._findings:
            detail = '\n'.join(self._tail) if code != 0 else tr('tlsNoResult')
            self._ctx.notifier.error(detail or tr('tlsFailed', code=code), title=title)

    def _rejected(self, error: MulitaError) -> None:
        self._fail(error)
