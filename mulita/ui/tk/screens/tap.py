from __future__ import annotations

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH

from mulita.core.models import TapConfig
from mulita.ui.tk.assets import Icon
from mulita.ui.tk.navigation import ScreenId
from mulita.ui.tk.screens.base import Screen
from mulita.ui.tk.widgets import OutputBox, RadioGroup, ToggleButton

# (titulo, separacion vertical del bloque)
_GROUPS = (
    ('Seleccion de interface Entrante', 8),
    ('Seleccion de interface Mirror', 8),
    ('Seleccion de interface Saliente', 5),
)


class TapScreen(Screen):
    screen_id = ScreenId.TAP
    title = 'TAP'

    def build(self) -> None:
        bar = self.top_bar(self.title)
        bar.add_button('Refresh', Icon.REFRESH, self._refresh_interfaces)
        self.add_share(bar, self.title)

        notebook = self.notebook(self.frame, style='primary')
        config_tab = ttk.Frame(notebook)
        screen_tab = ttk.Frame(notebook)

        self._groups: list[RadioGroup] = []
        for title, pady in _GROUPS:
            frame = ttk.Frame(config_tab)
            frame.pack(padx=5, pady=pady, fill=BOTH)
            group = RadioGroup(frame, title, radio_pady=10)
            group.frame.pack(pady=5, side='left')
            self._groups.append(group)
        self._refresh_interfaces()

        self._button = ToggleButton(config_tab, self._toggle, 'INICIAR', 'custom', padding=10, width=15)
        self._button.widget.pack(padx=20, pady=2)

        ttk.Frame(screen_tab).pack(fill=BOTH, pady=2)
        output_frame = ttk.Frame(screen_tab)
        output_frame.pack(pady=2, padx=5, fill=BOTH)
        self._output = OutputBox(output_frame, height=24, width=80)
        self._output.widget.pack(fill=BOTH)

        notebook.add(config_tab, text='Configuracion')
        notebook.add(screen_tab, text='Pantalla')

    def _refresh_interfaces(self) -> None:
        options = [(name, name) for name in self.services.interfaces.names()]
        for group in self._groups:
            group.set_options(options)

    def _toggle(self) -> None:
        tap = self.services.tap
        if tap.is_running:
            tap.stop()
        else:
            entrante, mirror, saliente = (group.value for group in self._groups)
            tap.start(TapConfig(entrante=entrante, mirror=mirror, saliente=saliente))
        self._button.set_active(tap.is_running)
