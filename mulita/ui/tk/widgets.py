from __future__ import annotations

import tkinter as tk
from typing import Callable, Sequence

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, END
from ttkbootstrap.scrolled import ScrolledText

from mulita.ui.tk.assets import Icon
from mulita.ui.tk.context import ScreenContext

Option = tuple[str, str]


class TopBar:
    """Titulo, VOLVER y TECLADO. Los botones extra se agregan a la izquierda de estos."""

    def __init__(self, parent: tk.Misc, title: str, ctx: ScreenContext):
        self._ctx = ctx
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=BOTH)

        ttk.Label(self.frame, text=title, font=('Helvetica', 25)).pack(padx=5, pady=0, side='left')
        self.add_button('VOLVER', Icon.BACK, ctx.navigator.go_home)
        self._keyboard = self.add_button('TECLADO', Icon.KEYBOARD, ctx.services.keyboard.toggle)
        ctx.services.keyboard.subscribe(ctx.dispatcher.wrap(self._show_keyboard_state))

    def add_button(self, text: str, icon: Icon, command: Callable[[], None]) -> ttk.Button:
        button = ttk.Button(self.frame, text=text, style='barraSuperior.primary.TButton',
                            command=command, image=self._ctx.assets.icon(icon))
        button.pack(padx=5, pady=0, side='right')
        return button

    def _show_keyboard_state(self, visible: bool) -> None:
        color = 'danger' if visible else 'primary'
        self._keyboard.configure(style=f'barraSuperior.{color}.TButton')


class ToggleButton:
    """Verde con el texto de inicio; rojo con DETENER mientras algo corre."""

    def __init__(self, parent: tk.Misc, command: Callable[[], None], idle_text: str,
                 style_family: str, active_text: str = 'DETENER', **options):
        self._idle = (idle_text, f'{style_family}.success.TButton')
        self._active = (active_text, f'{style_family}.danger.TButton')
        self.widget = ttk.Button(parent, text=self._idle[0], style=self._idle[1],
                                 command=command, **options)

    def set_active(self, active: bool) -> None:
        text, style = self._active if active else self._idle
        self.widget.configure(text=text, style=style)


class RadioGroup:

    def __init__(self, parent: tk.Misc, title: str, radio_pady: int = 10):
        self._radio_pady = radio_pady
        self._variable = tk.StringVar()
        self._radios: list[ttk.Radiobutton] = []
        self.frame = ttk.Labelframe(parent, text=title, padding=5)

    @property
    def value(self) -> str:
        return self._variable.get()

    def set_options(self, options: Sequence[Option]) -> None:
        for radio in self._radios:
            radio.destroy()
        values = {value for _, value in options}
        if self._variable.get() not in values:
            self._variable.set('')
        self._radios = []
        for label, value in options:
            radio = ttk.Radiobutton(self.frame, style='my.primary.TRadiobutton',
                                    variable=self._variable, text=label, value=value)
            radio.pack(pady=self._radio_pady, padx=8, side='left')
            self._radios.append(radio)


class OutputBox:

    def __init__(self, parent: tk.Misc, height: int = 15, width: int = 80,
                 font=('Courier', 11), scrolled: bool = False):
        if scrolled:
            self.widget = ScrolledText(parent, height=height, width=width, hbar=True)
            self._text = getattr(self.widget, 'text', self.widget)
        else:
            self.widget = tk.Text(parent, height=height, width=width, font=font)
            self._text = self.widget

    def clear(self) -> None:
        self._text.delete(1.0, END)

    def append(self, text: str) -> None:
        self._text.insert(END, text)
        self._text.see(END)

    def show(self, text: str) -> None:
        self.clear()
        self.append(text)


class TargetBar:
    """Etiqueta, campo de texto y boton de accion alineados a la derecha."""

    def __init__(self, parent: tk.Misc, label: str, button_text: str,
                 command: Callable[[], None], entry_width: int = 34, button_padx: int = 23,
                 button_width: int | None = None, fill: bool = True, toggle: bool = False):
        self.frame = ttk.Frame(parent)
        if fill:
            self.frame.pack(fill=BOTH, pady=2)
        else:
            self.frame.pack(pady=2, padx=2)

        button_options = {'width': button_width} if button_width else {}
        self.toggle: ToggleButton | None = None
        if toggle:
            self.toggle = ToggleButton(self.frame, command, button_text, 'destino', **button_options)
            self.button = self.toggle.widget
        else:
            self.button = ttk.Button(self.frame, text=button_text, style='destino.success.TButton',
                                     command=command, **button_options)
        self.button.pack(padx=button_padx, pady=10, side='right')

        self.entry = ttk.Entry(self.frame, width=entry_width, font=('Courier', 15))
        self.entry.pack(pady=10, side='right')

        ttk.Label(self.frame, text=label, style='destino.TLabel').pack(side='right')

    @property
    def value(self) -> str:
        return self.entry.get()

    def set_busy(self, busy: bool) -> None:
        self.button.configure(state='disabled' if busy else 'normal')


class LabeledScale:

    def __init__(self, parent: tk.Misc, length: int, minimum: float, maximum: float,
                 initial: float, formatter: Callable[[float], str]):
        self._formatter = formatter
        self._label: ttk.Label | None = None
        frame = ttk.Frame(parent)
        frame.pack(side='left', padx=10)
        self._scale = ttk.Scale(frame, length=length, orient='horizontal',
                                from_=minimum, to=maximum, command=self._refresh)
        self._scale.set(initial)
        self._scale.pack()
        self._label = ttk.Label(frame, text=formatter(self.value))
        self._label.pack()

    @property
    def value(self) -> float:
        return float(self._scale.get())

    def _refresh(self, _value: str) -> None:
        if self._label is not None:
            self._label.config(text=self._formatter(self.value))
