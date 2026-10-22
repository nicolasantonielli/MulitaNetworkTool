from __future__ import annotations

import ttkbootstrap as ttk

from mulita.ui.tk.navigation import ScreenId
from mulita.ui.tk.screens.base import Screen

# (texto, destino, fila, columna, opciones de grid)
_BUTTONS = (
    ('CAPTURA PAQUETES', ScreenId.CAPTURE, 1, 0, {'padx': 17, 'pady': 5}),
    ('TRAZAS', ScreenId.TRACES, 1, 1, {}),
    ('TAP', ScreenId.TAP, 2, 0, {'pady': 10}),
    ('ESCANEO', ScreenId.SCAN, 2, 1, {}),
    ('HERRAMIENTAS', ScreenId.TOOLS, 3, 0, {}),
    ('CONFIG', ScreenId.CONFIG, 3, 1, {'pady': 10}),
)


class HomeScreen(Screen):
    screen_id = ScreenId.HOME

    def build(self) -> None:
        for text, target, row, column, grid in _BUTTONS:
            ttk.Button(self.frame, text=text, style='myhome.primary.Outline.TButton',
                       command=lambda target=target: self.ctx.navigator.show(target)
                       ).grid(row=row, column=column, **grid)
