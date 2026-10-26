from __future__ import annotations

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH

from mulita.core.errors import MulitaError
from mulita.core.models import PING_COUNT, PING_INTERVAL, PING_SIZE
from mulita.presentation import texts
from mulita.ui.tk.navigation import ScreenId
from mulita.ui.tk.screens.base import Screen
from mulita.ui.tk.widgets import LabeledScale, OutputBox, TargetBar


class TracesScreen(Screen):
    screen_id = ScreenId.TRACES
    title = 'TRAZAS'

    def build(self) -> None:
        self.add_share(self.top_bar(self.title), self.title)

        notebook = self.notebook(self.frame, style='primary')
        trace_tab = ttk.Frame(notebook)
        ping_tab = ttk.Frame(notebook)
        self._build_trace(trace_tab)
        self._build_ping(ping_tab)
        notebook.add(trace_tab, text='Trazas')
        notebook.add(ping_tab, text='Ping')

    # Pestaña Trazas

    def _build_trace(self, tab: ttk.Frame) -> None:
        self._trace_target = TargetBar(tab, 'IP DESTINO', 'TRAZADO', self._trace)
        frame = ttk.Frame(tab)
        frame.pack(pady=2, padx=5)
        self._trace_output = OutputBox(frame)
        self._trace_output.widget.pack(fill=BOTH)

    def _trace(self) -> None:
        target = self._trace_target.value
        self._trace_output.show(texts.TRACING)
        self._trace_target.set_busy(True)
        self.run_in_background(lambda: self.services.trace.trace(target),
                               self._trace_done, self._trace_failed)

    def _trace_done(self, hops) -> None:
        if not hops:
            self._trace_output.show('Sin saltos\n')
        else:
            lines = [
                f'{hop.hop:>2}  {hop.address:<16}  {hop.loss:>7}  med {hop.average}'
                for hop in hops
            ]
            self._trace_output.show('\n'.join(lines) + '\n')
        self._trace_target.set_busy(False)

    def _trace_failed(self, error: Exception) -> None:
        self._trace_output.show(f'{error}\n')
        self._trace_target.set_busy(False)

    # Pestaña Ping

    def _build_ping(self, tab: ttk.Frame) -> None:
        self._ping_target = TargetBar(tab, 'IP DESTINO', 'PING', self._toggle_ping,
                                      button_width=13, toggle=True)

        settings = ttk.Frame(tab)
        settings.pack(pady=2, padx=5)
        self._count = LabeledScale(settings, 200, PING_COUNT.minimum, PING_COUNT.maximum,
                                   PING_COUNT.default, texts.ping_count)
        self._interval = LabeledScale(settings, 250, PING_INTERVAL.minimum, PING_INTERVAL.maximum,
                                      PING_INTERVAL.default, texts.ping_interval)
        self._size = LabeledScale(settings, 200, PING_SIZE.minimum, PING_SIZE.maximum,
                                  PING_SIZE.default, texts.ping_size)

        frame = ttk.Frame(tab)
        frame.pack(pady=2, padx=5)
        self._ping_output = OutputBox(frame, height=13, width=73, scrolled=True)
        self._ping_output.widget.pack(fill=BOTH)

    def _toggle_ping(self) -> None:
        ping = self.services.ping
        if ping.is_running:
            ping.stop()
            self._ping_target.toggle.set_active(False)
            return

        self._ping_output.clear()
        try:
            ping.start(self._ping_target.value, self._count.value, self._interval.value, self._size.value,
                       on_output=self.ctx.dispatcher.wrap(self._ping_output.append),
                       on_exit=self.ctx.dispatcher.wrap(self._ping_finished))
        except MulitaError as exc:
            self._ping_output.show(f'{exc}\n')
            return
        self._ping_target.toggle.set_active(True)

    def _ping_finished(self, _code: int) -> None:
        if not self.services.ping.is_running:
            self._ping_target.toggle.set_active(False)
