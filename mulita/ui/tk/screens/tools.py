from __future__ import annotations

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH

from mulita.presentation import texts
from mulita.ui.tk.navigation import ScreenId
from mulita.ui.tk.screens.base import Screen
from mulita.ui.tk.widgets import OutputBox, TargetBar


class ToolsScreen(Screen):
    screen_id = ScreenId.TOOLS
    title = 'HERRAMIENTAS'

    def build(self) -> None:
        self.add_share(self.top_bar(self.title), self.title)

        notebook = self.notebook(self.frame, bootstyle='primary')
        tabs = (
            ('Wake on Lan', self._build_wake_on_lan),
            ('Temperatura ambiente', self._build_climate),
            ('Test de velocidad', self._build_speed_test),
            ('Ip Publica', self._build_public_ip),
        )
        for text, build_tab in tabs:
            tab = ttk.Frame(notebook)
            build_tab(tab)
            notebook.add(tab, text=text)

    # Pestaña Wake on Lan

    def _build_wake_on_lan(self, tab: ttk.Frame) -> None:
        self._mac = TargetBar(tab, 'MAC DESTINO', 'DESPERTAR', self._wake,
                              entry_width=30, button_padx=20, fill=False)
        frame = ttk.Frame(tab)
        frame.pack(pady=2, padx=5)
        self._wol_output = OutputBox(frame)
        self._wol_output.widget.pack()

    def _wake(self) -> None:
        mac = self._mac.value
        self._wol_output.clear()
        self._mac.set_busy(True)
        self.run_in_background(lambda: self.services.wake_on_lan.wake(mac),
                               self._wake_done, self._wake_done)

    def _wake_done(self, output) -> None:
        self._wol_output.show(f'{output}')
        self._mac.set_busy(False)

    # Pestaña Temperatura ambiente

    def _build_climate(self, tab: ttk.Frame) -> None:
        self._temperature = ttk.Label(tab, text=' ', padding=10, font=('Helvetica', 18))
        self._temperature.pack(pady=30)
        self._humidity = ttk.Label(tab, text=' ', padding=10, font=('Helvetica', 18))
        self._humidity.pack(pady=10)
        ttk.Button(tab, text='ACTUALIZAR', padding=4, style='destino.success.TButton',
                   command=self._read_climate).pack(padx=10, pady=10)
        self._read_climate()

    def _read_climate(self) -> None:
        self.run_in_background(self.services.climate.read, self._show_climate,
                               lambda _error: self._show_climate(None))

    def _show_climate(self, reading) -> None:
        self._temperature.config(text=texts.temperature(reading))
        self._humidity.config(text=texts.humidity(reading))

    # Pestaña Test de velocidad

    def _build_speed_test(self, tab: ttk.Frame) -> None:
        controls = ttk.Frame(tab)
        controls.pack(pady=20, padx=2)
        self._speed_button = ttk.Button(controls, text='TEST DE VELOCIDAD', style='custom.success.TButton',
                                        command=self._measure)
        self._speed_button.pack(padx=15, pady=10, side='right')

        results = ttk.Frame(tab)
        results.pack(pady=15, padx=5)
        self._measuring = ttk.Label(results, text='', font=('helvetica', 15), style='primary.Tlabel')
        self._measuring.pack(pady=5)
        self._upload = ttk.Label(results, text='', font=('helvetica', 25), style='success.Tlabel')
        self._upload.pack(pady=10)
        self._download = ttk.Label(results, text='', font=('helvetica', 25), style='success.Tlabel')
        self._download.pack()

    def _measure(self) -> None:
        self._measuring.config(text=texts.MEASURING)
        self._speed_button.configure(state='disabled')
        self.run_in_background(self.services.speed_test.measure, self._show_speed, self._speed_failed)

    def _show_speed(self, result) -> None:
        self._download.config(text=texts.download(result))
        self._upload.config(text=texts.upload(result))
        self._measuring.config(text='')
        self._speed_button.configure(state='normal')

    def _speed_failed(self, error: Exception) -> None:
        self._measuring.config(text=str(error))
        self._speed_button.configure(state='normal')

    # Pestaña Ip Publica

    def _build_public_ip(self, tab: ttk.Frame) -> None:
        self._public_ip = ttk.Label(tab, text=' ', padding=10, font=('Helvetica', 18))
        self._public_ip.pack(pady=40)
        ttk.Button(tab, text='ACTUALIZAR', padding=4, style='destino.success.TButton',
                   command=self._lookup_public_ip).pack(padx=10, pady=10)

    def _lookup_public_ip(self) -> None:
        self.run_in_background(self.services.public_ip.lookup,
                               lambda info: self._public_ip.config(text=texts.public_ip(info.ip)),
                               lambda error: self._public_ip.config(text=str(error)))
