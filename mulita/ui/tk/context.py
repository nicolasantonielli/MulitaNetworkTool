from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mulita.config import AppConfig
from mulita.services import Services
from mulita.ui.tk.assets import Assets
from mulita.ui.tk.dispatcher import TkDispatcher
from mulita.ui.tk.navigation import Navigator
from mulita.ui.tk.notifier import ToastNotifier
from mulita.ui.tk.styles import StyleManager


@dataclass
class ScreenContext:
    config: AppConfig
    services: Services
    dispatcher: TkDispatcher
    navigator: Navigator
    assets: Assets
    notifier: ToastNotifier
    styles: StyleManager
    close_app: Callable[[], None]
