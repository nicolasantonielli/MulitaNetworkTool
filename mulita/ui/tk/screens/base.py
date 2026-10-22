from __future__ import annotations

import tkinter as tk
from abc import ABC, abstractmethod

import ttkbootstrap as ttk

from mulita.ui.tk.assets import Icon
from mulita.ui.tk.context import ScreenContext
from mulita.ui.tk.navigation import ScreenId
from mulita.ui.tk.widgets import TopBar


class Screen(ABC):
    screen_id: ScreenId

    def __init__(self, parent: tk.Misc, ctx: ScreenContext):
        self.ctx = ctx
        self.services = ctx.services
        self.frame = ttk.Frame(parent)
        self.frame.grid(row=0, column=0, sticky='nsew', padx=0, pady=10)
        ctx.navigator.register(self.screen_id, self.frame)
        self.build()

    @abstractmethod
    def build(self) -> None: ...

    def top_bar(self, title: str) -> TopBar:
        return TopBar(self.frame, title, self.ctx)

    def add_share(self, bar: TopBar, source: str) -> None:
        bar.add_button('SHARE', Icon.SHARE, lambda: self.services.share.share(source))

    def run_in_background(self, task, on_success, on_error=None) -> None:
        self.ctx.dispatcher.background(task, on_success, on_error or self.show_error)

    def show_error(self, error: Exception) -> None:
        self.ctx.notifier.error(str(error))

    @staticmethod
    def notebook(parent: tk.Misc, **options) -> ttk.Notebook:
        notebook = ttk.Notebook(parent, **options)
        notebook.pack(padx=10, pady=2, fill='both')
        return notebook
