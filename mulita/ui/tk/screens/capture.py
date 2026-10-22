from __future__ import annotations

from collections import deque

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, END

from mulita.core.errors import MulitaError
from mulita.core.models import CaptureDirection
from mulita.ui.tk.navigation import ScreenId
from mulita.ui.tk.screens.base import Screen
from mulita.ui.tk.widgets import RadioGroup, ToggleButton


class CaptureScreen(Screen):
    screen_id = ScreenId.CAPTURE
    title = 'CAPTURA DE PAQUETES'

    def build(self) -> None:
        self.add_share(self.top_bar(self.title), self.title)
        self._last_output: deque[str] = deque(maxlen=3)
        self._stopping = False

        selection = ttk.Frame(self.frame)
        selection.pack(padx=10, pady=30, fill=BOTH)

        self._interfaces = RadioGroup(selection, 'Seleccion de Interface', radio_pady=15)
        self._interfaces.frame.pack(pady=5, side='left')
        self._interfaces.set_options([(name, name) for name in self.services.interfaces.names()])

        self._directions = RadioGroup(selection, 'Seleccion de dirección', radio_pady=15)
        self._directions.frame.pack(pady=5, padx=10, side='left')
        self._directions.set_options([(direction.label, direction.value) for direction in CaptureDirection])

        file_frame = ttk.Frame(self.frame)
        file_frame.pack(padx=5, pady=10, fill=BOTH)
        file_group = ttk.Labelframe(file_frame, text='Nombre de archivo', padding=5)
        file_group.pack(pady=5, side='left')
        self._filename = ttk.Entry(file_group, width=25, font=('Courier', 13))
        self._filename.insert(END, self.ctx.config.default_capture_name)
        self._filename.pack()

        control = ttk.Frame(self.frame)
        control.pack(padx=5, pady=20, fill=BOTH)
        self._button = ToggleButton(control, self._toggle, 'INICIAR', 'custom', padding=10, width=15)
        self._button.widget.pack(padx=20, pady=10, side='right')

    def _toggle(self) -> None:
        capture = self.services.capture
        if capture.is_running:
            self._stopping = True
            capture.stop()
            self._button.set_active(False)
            return

        self._last_output.clear()
        self._stopping = False
        try:
            capture.start(self._interfaces.value, self._directions.value, self._filename.get(),
                          on_output=self._last_output.append,
                          on_exit=self.ctx.dispatcher.wrap(self._finished))
        except MulitaError as exc:
            self.show_error(exc)
            return
        self._button.set_active(True)

    def _finished(self, code: int) -> None:
        if self.services.capture.is_running:
            return
        self._button.set_active(False)
        if code != 0 and not self._stopping:
            detail = ''.join(self._last_output).strip() or f'tcpdump termino con codigo {code}'
            self.ctx.notifier.error(detail, title='Captura')
