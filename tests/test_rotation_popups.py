from pathlib import Path
from types import SimpleNamespace
import unittest
from PyQt5 import sip
from PyQt5.QtCore import QObject, QPointF, QUrl, QMetaObject
from PyQt5.QtQml import QQmlEngine, QQmlComponent
from PyQt5.QtQuick import QQuickItem
from PyQt5.QtTest import QTest
from tests.qt_support import qt_app
from mulita.config import AppConfig
from mulita.services.settings import SettingsService
from tests.fakes import FakeBacklight
from mulita.adapters.settings_store import MemorySettingsStore
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.system import Appearance, I18nController

QML = b'''import QtQuick 2.15
import QtQuick.Controls 2.15
import "../mulita/ui/qt/qml/components"
ApplicationWindow {
    id:w; width:800; height:480; visible:true
    RotatedSurface {
        id:scene;angle:ui.rotation
        ConfirmDialog {id:dialog; title:"Confirm";message:"Testing"}
        ComboBox {id:combo; x:20;y:60;width:200;model:["A","B"]}
    }
    function showDialog(){dialog.open()}
    function closeDialog(){dialog.close()}
    function showCombo(){combo.popup.open()}
    function closeCombo(){combo.popup.close()}
    OverlayRotation { overlay:w.Overlay.overlay; surface:scene }
}'''

class PopupRotationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=qt_app()
    def test_popup_rotation(self):
        service=SettingsService(MemorySettingsStore(), FakeBacklight())
        ctx=BridgeContext(AppConfig(test_mode=True), getattr(SimpleNamespace(settings=service), 'settings', None), None, Notifier())
        ui=Appearance(ctx);i18n=I18nController(ctx)
        engine=QQmlEngine()
        engine.rootContext().setContextProperty('ui',ui)
        engine.rootContext().setContextProperty('i18n',i18n)
        c=QQmlComponent(engine)
        c.setData(QML,QUrl.fromLocalFile(str(Path(__file__).resolve())))
        self.assertEqual(c.errors(),[])
        window=c.create()
        self.assertIsNotNone(window)
        try:
            for angle in (0,90,180,270):
                service.set_rotation(angle);QTest.qWait(30)
                window.setWidth(900 if angle in (90,270) else 800)
                window.setHeight(540 if angle in (90,270) else 480)
                QTest.qWait(30)
                for kind in ('Dialog','Combo'):
                    QMetaObject.invokeMethod(window,'show'+kind);QTest.qWait(150)
                    obj=next(o for o in window.findChildren(QObject) if o.metaObject().className()=='QQuickOverlay')
                    overlay=sip.cast(obj,QQuickItem)
                    self.assertEqual(overlay.rotation(),angle)
                    expected=(window.height(),window.width()) if angle in (90,270) else (window.width(),window.height())
                    self.assertEqual((overlay.width(),overlay.height()),expected)
                    popup_items = [item for item in overlay.childItems()
                                   if 'PopupItem' in item.metaObject().className() and item.isVisible()]
                    self.assertTrue(popup_items)
                    for item in popup_items:
                        if 'PopupItem' in item.metaObject().className():
                            a=item.mapToScene(QPointF(0,0));b=item.mapToScene(QPointF(100,0))
                            expected_axis={0:(100,0),90:(0,100),180:(-100,0),270:(0,-100)}[angle]
                            self.assertAlmostEqual(b.x()-a.x(),expected_axis[0])
                            self.assertAlmostEqual(b.y()-a.y(),expected_axis[1])
                            for corner in (QPointF(0,0),QPointF(item.width(),item.height())):
                                point=item.mapToScene(corner)
                                self.assertTrue(-1<=point.x()<=window.width()+1,(angle,kind,point))
                                self.assertTrue(-1<=point.y()<=window.height()+1,(angle,kind,point))
                    QMetaObject.invokeMethod(window,'close'+kind);QTest.qWait(150)
        finally:
            window.close();sip.delete(window)
