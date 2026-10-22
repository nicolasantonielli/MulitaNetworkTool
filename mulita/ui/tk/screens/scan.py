from __future__ import annotations

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH

from mulita.core.errors import MulitaError
from mulita.presentation import texts
from mulita.ui.tk.navigation import ScreenId
from mulita.ui.tk.screens.base import Screen
from mulita.ui.tk.widgets import OutputBox, TargetBar, ToggleButton


class ScanScreen(Screen):
    screen_id = ScreenId.SCAN
    title = 'ESCANEO'

    def build(self) -> None:
        self.add_share(self.top_bar(self.title), self.title)

        notebook = self.notebook(self.frame, bootstyle='primary')
        scan_tab = ttk.Frame(notebook)
        discovery_tab = ttk.Frame(notebook)
        self._build_scan(scan_tab)
        self._build_discovery(discovery_tab)
        notebook.add(scan_tab, text='Escaneo de puertos')
        notebook.add(discovery_tab, text='Descubrimiento IP')

    # Pestaña Escaneo de puertos

    def _build_scan(self, tab: ttk.Frame) -> None:
        self._scan_target = TargetBar(tab, 'IP DESTINO', 'ESCANEAR', self._scan)
        frame = ttk.Frame(tab)
        frame.pack(pady=2, padx=5)
        self._scan_output = OutputBox(frame)
        self._scan_output.widget.pack(fill=BOTH)

    def _scan(self) -> None:
        arguments = self._scan_target.value
        self._scan_output.show(texts.SCANNING)
        self._scan_target.set_busy(True)
        self.run_in_background(lambda: self.services.port_scan.scan(arguments),
                               self._scan_done, self._scan_done)

    def _scan_done(self, output) -> None:
        self._scan_output.show(f'{output}')
        self._scan_target.set_busy(False)

    # Pestaña Descubrimiento IP

    def _build_discovery(self, tab: ttk.Frame) -> None:
        controls = ttk.Frame(tab)
        controls.pack(pady=2, padx=2)
        self._discovery_button = ToggleButton(controls, self._toggle_discovery, 'DESCUBRIMIENTO IP',
                                              'destino', padding=10, width=20)
        self._discovery_button.widget.pack(padx=20, pady=10, side='right')

        frame = ttk.Frame(tab)
        frame.pack(pady=2, padx=5)
        self._discovery_output = OutputBox(frame)
        self._discovery_output.widget.pack(fill=BOTH)

    def _toggle_discovery(self) -> None:
        discovery = self.services.discovery
        if discovery.is_running:
            discovery.stop()
            self._discovery_button.set_active(False)
            return

        self._discovery_output.clear()
        try:
            discovery.start(on_output=self.ctx.dispatcher.wrap(self._discovery_output.append),
                            on_exit=self.ctx.dispatcher.wrap(self._discovery_finished))
        except MulitaError as exc:
            self._discovery_output.show(f'{exc}\n')
            return
        self._discovery_button.set_active(True)

    def _discovery_finished(self, _code: int) -> None:
        if not self.services.discovery.is_running:
            self._discovery_button.set_active(False)
