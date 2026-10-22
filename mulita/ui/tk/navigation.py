from __future__ import annotations

from enum import Enum, auto
from tkinter import Misc


class ScreenId(Enum):
    HOME = auto()
    CAPTURE = auto()
    TRACES = auto()
    TAP = auto()
    SCAN = auto()
    TOOLS = auto()
    CONFIG = auto()


class Navigator:

    def __init__(self):
        self._frames: dict[ScreenId, Misc] = {}

    def register(self, screen: ScreenId, frame: Misc) -> None:
        self._frames[screen] = frame

    def show(self, screen: ScreenId) -> None:
        self._frames[screen].tkraise()

    def go_home(self) -> None:
        self.show(ScreenId.HOME)
