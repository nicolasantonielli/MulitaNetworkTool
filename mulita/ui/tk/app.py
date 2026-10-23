from __future__ import annotations

import sys

import ttkbootstrap as ttk
from PIL import Image

from mulita.config import AppConfig
from mulita.services import Services
from mulita.ui.tk.assets import Assets
from mulita.ui.tk.context import ScreenContext
from mulita.ui.tk.dispatcher import TkDispatcher
from mulita.ui.tk.navigation import Navigator
from mulita.ui.tk.notifier import ToastNotifier
from mulita.ui.tk.screens import ALL_SCREENS
from mulita.ui.tk.styles import StyleManager

# ttkbootstrap todavia usa Image.CUBIC, eliminado en Pillow 10
if not hasattr(Image, 'CUBIC'):
    Image.CUBIC = Image.BICUBIC


class TkApplication:

    def __init__(self, config: AppConfig, services: Services):
        self._services = services
        self.root = ttk.Window(title=config.window_title, themename=config.default_theme)
        # En Windows con DPI alto, Tk puede inflar fuentes/controles y recortar la UI
        # al forzar 800x480. En modo test fijamos escala base para simular mejor la Pi.
        if config.test_mode and sys.platform == 'win32':
            self.root.tk.call('tk', 'scaling', 1.0)
        self.root.geometry(f'{config.window_width}x{config.window_height}')
        self.root.resizable(config.test_mode, config.test_mode)
        if not config.test_mode:
            self.root.wm_attributes('-fullscreen', True)

        styles = StyleManager(ttk.Style())
        styles.apply(config.default_theme)

        navigator = Navigator()
        context = ScreenContext(
            config=config,
            services=services,
            dispatcher=TkDispatcher(self.root),
            navigator=navigator,
            assets=Assets(config.assets_dir),
            notifier=ToastNotifier(),
            styles=styles,
            close_app=self.close,
        )
        self.screens = [screen(self.root, context) for screen in ALL_SCREENS]
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        navigator.go_home()

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        try:
            self._services.shutdown()
        finally:
            self.root.destroy()
