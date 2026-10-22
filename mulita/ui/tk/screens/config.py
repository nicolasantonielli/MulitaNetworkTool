from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH

from mulita.presentation import texts
from mulita.ui.tk.navigation import ScreenId
from mulita.ui.tk.screens.base import Screen
from mulita.version import __version__


class ConfigScreen(Screen):
    screen_id = ScreenId.CONFIG
    title = 'CONFIGURACIÓN'

    def build(self) -> None:
        self.top_bar(self.title)

        notebook = ttk.Notebook(self.frame, bootstyle='primary', height=365)
        notebook.pack(padx=10, pady=2, fill=BOTH)
        tabs = (
            ('General', self._build_general),
            ('Wifi', self._build_pending),
            ('Ethernet Interna', self._build_pending),
            ('Ethernet Externa', self._build_pending),
            ('Mantenimiento', self._build_maintenance),
        )
        for text, build_tab in tabs:
            tab = ttk.Frame(notebook)
            build_tab(tab)
            notebook.add(tab, text=text)

    # Pestaña General

    def _build_general(self, tab: ttk.Frame) -> None:
        themes = ttk.Menubutton(tab, text='ESTILO', bootstyle='primary')
        themes.pack(pady=15)

        self._theme = tk.StringVar(value=self.ctx.styles.current)
        menu = ttk.Menu(themes, font=('helvetica', 18))
        for theme in self.ctx.config.themes:
            menu.add_radiobutton(label=theme, value=theme, variable=self._theme,
                                 command=lambda theme=theme: self.ctx.styles.apply(theme))
        themes['menu'] = menu

        ttk.Button(tab, text='APLICAR', style='destino.success.TButton',
                   command=lambda: self.ctx.styles.apply(self._theme.get())).pack(pady=20)

    # Pestañas Wifi y Ethernet, sin configuracion todavia

    def _build_pending(self, tab: ttk.Frame) -> None:
        ttk.Button(tab, text='APLICAR', style='destino.success.TButton',
                   command=self.ctx.navigator.go_home).pack(pady=20)

    # Pestaña Mantenimiento

    def _build_maintenance(self, tab: ttk.Frame) -> None:
        maintenance = self.services.maintenance
        buttons = (
            ('CERRAR', 'danger', self.ctx.close_app),
            ('REINICIAR', 'danger', lambda: self.run_in_background(maintenance.reset, None)),
            ('ACTUALIZAR', 'success', lambda: self.run_in_background(maintenance.update, self._updated)),
            ('APAGAR', 'danger', lambda: self.run_in_background(maintenance.poweroff, None)),
        )
        for text, color, command in buttons:
            ttk.Button(tab, text=text, width=12, style=f'destino.{color}.TButton',
                       command=command).pack(pady=10)

        ttk.Label(tab, text=texts.version(__version__), font=('helvetica', 12)).pack(pady=5)

    def _updated(self, _result) -> None:
        self.ctx.notifier.info('Update', texts.UPDATE_DONE)
