from __future__ import annotations

import ttkbootstrap as ttk


class StyleManager:
    """Los estilos propios se pierden al cambiar de tema: se reaplican en cada cambio."""

    def __init__(self, style: ttk.Style):
        self._style = style
        self.current = ''

    def apply(self, theme: str) -> None:
        self._style.theme_use(theme)
        self.current = theme
        self._configure()

    def _configure(self) -> None:
        style = self._style

        # Botones Home
        style.configure('myhome.primary.Outline.TButton', font=('helvetica', 18),
                        padding=53, width=20, relief='raised', borderwidth=4)

        # Botones
        for color in ('success', 'primary', 'danger'):
            style.configure(f'custom.{color}.TButton', font=('helvetica', 15))
        for color in ('primary', 'danger', 'success'):
            style.configure(f'barraSuperior.{color}.TButton', font=('helvetica', 15), padding=8)

        # Pestañas
        style.configure('my.primary.TNotebook.Label', font=('helvetica', 18))

        # Frame destino
        for color in ('success', 'danger'):
            style.configure(f'destino.{color}.TButton', font=('helvetica', 14), padding=7, width=15)
        style.configure('destino.TLabel', font=('helvetica', 14), padding=7)
