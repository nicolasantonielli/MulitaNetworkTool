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

        from mulita.ui.qt.bridge.activity import ActivityController, TechnicalJournal
        from mulita.ui.qt.bridge.remote import RemoteControl
        from mulita.ui.qt.bridge.base import BridgeContext, Notifier
        from mulita.ui.qt.bridge.ethernet import InternalEthernetController
        from mulita.ui.qt.bridge.ipv4 import IPv4Controller
        from mulita.ui.qt.bridge.diagnostics import (DiscoveryController,
                                                     PingController,
                                                     PortScanController,
                                                     TraceController)
        from mulita.ui.qt.bridge.network import (CaptureController,
                                                 NetworkController,
                                                 TapController)
        from mulita.ui.qt.bridge.servers import ServersController
        from mulita.ui.qt.bridge.nmapscan import NmapController
        from mulita.ui.qt.bridge.tls import TlsController
        from mulita.ui.qt.bridge.switchport import SwitchPortController
        from mulita.ui.qt.bridge.system import (Appearance, I18nController,
                                                SettingsController, SystemController)
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
        from mulita.ui.qt.touch_test import TouchTest
        from mulita.ui.qt.text_copy import TextCopyController

        self._services = services
        self.app = QGuiApplication(sys.argv)
        self.app.setApplicationName('Mulita')
        log_input_devices()
        self._pointer_cursor = False
        # Linux tambien puede correr con escritorio: DISPLAY no indica que haya mouse.
        self._cursor_follows_mouse = (
            Path('/proc/bus/input/devices').exists()
            and not config.test_mode)
        if self._cursor_follows_mouse:
            self.app.setOverrideCursor(QCursor(Qt.BlankCursor))
            self._cursor_timer = QTimer(self.app)
            self._cursor_timer.setInterval(1000)
            self._cursor_timer.timeout.connect(self._sync_cursor)
            self._sync_cursor()
            self._cursor_timer.start()
        self._touch_test = TouchTest()
        self._touch_debug = TouchDebug(self._touch_test)
        self.app.installEventFilter(self._touch_debug)
        self._text_copy = TextCopyController()
        self.app.installEventFilter(self._text_copy)

        notifier = Notifier()
        ctx = BridgeContext(config=config, settings=services.settings, dispatcher=QtDispatcher(), notifier=notifier)
        activity = ActivityController(ctx)
        self._remote = RemoteControl(lambda: self.root)
        notifier.activityRecorded.connect(activity.record)
        journal = TechnicalJournal(ctx, services.journal)
        self._controllers = {
            'remoteControl': self._remote,
            'activity': activity,
            'technicalJournal': journal,
            'textCopy': self._text_copy,
            'touchTest': self._touch_test,
            'ui': Appearance(ctx),
            'i18n': I18nController(ctx),
            'notifier': notifier,
            'settings': SettingsController(ctx),
            'system': SystemController(ctx, services.maintenance, services.share),
            'network': NetworkController(ctx, services.interfaces),
            'interna': InternalEthernetController(ctx, services.ethernet),
            'wifiIp': IPv4Controller(ctx, services.wifi, lambda: 'Wi-Fi', 'wifiIp'),
            'wifi': WifiController(ctx, services.wifi),
            'capture': CaptureController(ctx, services.capture),
            'tap': TapController(ctx, services.tap),
            'trace': TraceController(ctx, services.trace),
            'ping': PingController(ctx, services.ping),
            'portScan': PortScanController(ctx, services.port_scan),
            'discovery': DiscoveryController(ctx, services.discovery),
            'wakeOnLan': WakeOnLanController(ctx, services.wake_on_lan),
            'climate': ClimateController(ctx, services.climate),
            'speedTest': SpeedTestController(ctx, services.speed_test),
            'publicIp': PublicIpController(ctx, services.public_ip),
            'macVendor': MacVendorController(ctx, services.mac_vendor),
            'files': FilesController(ctx, services.files),
            'servers': ServersController(ctx, services.servers),
            'tls': TlsController(ctx, services.tls),
            'nmapScan': NmapController(ctx, services.nmap),
            'switchPort': SwitchPortController(ctx, services.switchport),
        }

        self.engine = QQmlApplicationEngine()
        self.engine.warnings.connect(lambda warnings: [log.warning(w.toString()) for w in warnings])
        self.engine.addImageProvider('icon', IconProvider())
        context = self.engine.rootContext()
        for name, controller in self._controllers.items():
            context.setContextProperty(name, controller)

        self._dispatcher = ctx.dispatcher
        self.app.aboutToQuit.connect(self._shutdown)
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
        shape = Qt.ArrowCursor if present else Qt.BlankCursor
        current = self.app.overrideCursor()
        if present == self._pointer_cursor and current is not None and current.shape() == shape:
            return
        self._pointer_cursor = present
        if current is None:
            self.app.setOverrideCursor(QCursor(shape))
        else:
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

    def _shutdown(self) -> None:
        self._remote.close()
        try:
            self._services.shutdown()
        finally:
            self._dispatcher.shutdown()
            self._controllers['technicalJournal'].close()

    def dispose(self) -> None:
        """El motor QML se destruye antes que los controladores que sus vinculaciones leen."""
        from PyQt5 import sip
        self.app.removeEventFilter(self._touch_debug)
        self.app.removeEventFilter(self._text_copy)
        self._shutdown()
        if self.engine is not None and not sip.isdeleted(self.engine):
            sip.delete(self.engine)
        self.engine = None
