from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

from mulita.config import AppConfig
from mulita.services import Services

log = logging.getLogger(__name__)

QML_DIR = Path(__file__).resolve().parent / 'qml'


class QtApplication:

    def __init__(self, config: AppConfig, services: Services):
        # El plugin qtvirtualkeyboard abre una ventana propia. En EGLFS Qt
        # aborta: "OpenGL windows cannot be mixed with others".
        os.environ.pop('QT_IM_MODULE', None)
        os.environ['QT_QUICK_CONTROLS_STYLE'] = 'Material'
        # Se decide en caliente: oculto con el dedo, visible si hay un mouse.
        os.environ.pop('QT_QPA_EGLFS_HIDECURSOR', None)
        runtime = os.environ.get('XDG_RUNTIME_DIR')
        if not runtime and hasattr(os, 'getuid'):
            runtime = f'/tmp/runtime-{os.getuid()}'
            os.makedirs(runtime, mode=0o700, exist_ok=True)
            os.environ['XDG_RUNTIME_DIR'] = runtime

        from PyQt5.QtCore import Qt, QTimer, QUrl
        from PyQt5.QtGui import QCursor, QGuiApplication
        from PyQt5.QtQml import QQmlApplicationEngine

        from mulita.ui.qt.bridge.base import BridgeContext, Notifier
        from mulita.ui.qt.bridge.ethernet import InternalEthernetController
        from mulita.ui.qt.bridge.diagnostics import (DiscoveryController,
                                                     PingController,
                                                     PortScanController,
                                                     TraceController)
        from mulita.ui.qt.bridge.network import (CaptureController,
                                                 NetworkController,
                                                 TapController)
        from mulita.ui.qt.bridge.system import (Appearance, SettingsController,
                                                SystemController)
        from mulita.ui.qt.bridge.wifi import WifiController
        from mulita.ui.qt.bridge.tools import (ClimateController,
                                               FilesController,
                                               MacVendorController,
                                               PublicIpController,
                                               SpeedTestController,
                                               WakeOnLanController)
        from mulita.ui.qt.dispatcher import QtDispatcher
        from mulita.ui.qt.icons import IconProvider
        from mulita.ui.qt.touch_debug import TouchDebug, log_input_devices

        self._services = services
        self.app = QGuiApplication(sys.argv)
        self.app.setApplicationName('Mulita')
        log_input_devices()
        self._pointer_cursor = False
        # En el escritorio el cursor lo maneja el sistema. En la Pi, sin DISPLAY, el dedo no debe dibujar una flecha.
        self._cursor_follows_mouse = (
            Path('/proc/bus/input/devices').exists()
            and not os.environ.get('DISPLAY')
            and not os.environ.get('WAYLAND_DISPLAY'))
        if self._cursor_follows_mouse:
            self.app.setOverrideCursor(QCursor(Qt.BlankCursor))
            self._cursor_timer = QTimer(self.app)
            self._cursor_timer.setInterval(1000)
            self._cursor_timer.timeout.connect(self._sync_cursor)
            self._sync_cursor()
            self._cursor_timer.start()
        self._touch_debug = TouchDebug()
        self.app.installEventFilter(self._touch_debug)

        notifier = Notifier()
        ctx = BridgeContext(config=config, services=services, dispatcher=QtDispatcher(), notifier=notifier)
        self._controllers = {
            'ui': Appearance(ctx),
            'notifier': notifier,
            'settings': SettingsController(ctx),
            'system': SystemController(ctx),
            'network': NetworkController(ctx),
            'interna': InternalEthernetController(ctx),
            'wifi': WifiController(ctx),
            'capture': CaptureController(ctx),
            'tap': TapController(ctx),
            'trace': TraceController(ctx),
            'ping': PingController(ctx),
            'portScan': PortScanController(ctx),
            'discovery': DiscoveryController(ctx),
            'wakeOnLan': WakeOnLanController(ctx),
            'climate': ClimateController(ctx),
            'speedTest': SpeedTestController(ctx),
            'publicIp': PublicIpController(ctx),
            'macVendor': MacVendorController(ctx),
            'files': FilesController(ctx),
        }

        self.engine = QQmlApplicationEngine()
        self.engine.warnings.connect(lambda warnings: [log.warning(w.toString()) for w in warnings])
        self.engine.addImageProvider('icon', IconProvider())
        context = self.engine.rootContext()
        for name, controller in self._controllers.items():
            context.setContextProperty(name, controller)

        self.app.aboutToQuit.connect(services.shutdown)
        self.engine.load(QUrl.fromLocalFile(str(QML_DIR / 'Main.qml')))
        if not self.engine.rootObjects():
            raise RuntimeError('No se pudo cargar la interfaz QML')

        # Python solo atiende Ctrl+C cuando recupera el control del bucle de Qt
        signal.signal(signal.SIGINT, lambda *_: self.app.quit())
        self._signal_pump = QTimer()
        self._signal_pump.start(300)
        self._signal_pump.timeout.connect(lambda: None)

    def _sync_cursor(self) -> None:
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QCursor

        from mulita.ui.qt.touch_debug import connected_mice

        names = connected_mice()
        present = bool(names)
        if present == self._pointer_cursor:
            return
        self._pointer_cursor = present
        shape = Qt.ArrowCursor if present else Qt.BlankCursor
        self.app.changeOverrideCursor(QCursor(shape))
        if present:
            log.info('mouse conectado (%s), cursor visible', ', '.join(names))
        else:
            log.info('sin mouse, cursor oculto')

    @property
    def root(self):
        return self.engine.rootObjects()[0]

    def run(self) -> int:
        try:
            return self.app.exec_()
        finally:
            self.dispose()

    def dispose(self) -> None:
        """El motor QML se destruye antes que los controladores que sus vinculaciones leen."""
        from PyQt5 import sip
        if self.engine is not None and not sip.isdeleted(self.engine):
            sip.delete(self.engine)
        self.engine = None
