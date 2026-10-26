"""Un menu de copia comun para textos, campos y salidas de Qt Quick."""
from PyQt5 import sip
from PyQt5.QtCore import QObject, QEvent, QMetaObject, QPointF, Qt, QTimer, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QGuiApplication, QWindow
from PyQt5.QtQuick import QQuickWindow


_BLOCKED = object()


class TextCopyController(QObject):
    requested = pyqtSignal(str, float, float, arguments=['text', 'screenX', 'screenY'])
    menuVisibleChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._menu_visible = False
        self._target = None
        self._menu_target = None
        self._pressed = False
        self._held = False
        self._origin = QPointF()
        self._selection = None
        self._raw_touch = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(600)
        self._timer.timeout.connect(self._hold)
        QGuiApplication.clipboard().dataChanged.connect(self.menuVisibleChanged.emit)

    @pyqtProperty(bool, notify=menuVisibleChanged)
    def menuVisible(self):
        return self._menu_visible

    @pyqtProperty(bool, notify=menuVisibleChanged)
    def editable(self):
        item = self._menu_target
        return (item is not None and not sip.isdeleted(item) and item.isEnabled()
                and item.isVisible() and self._is_editor(item)
                and not item.property('readOnly'))

    @pyqtProperty(bool, notify=menuVisibleChanged)
    def canPaste(self):
        return self.editable and bool(QGuiApplication.clipboard().text())

    @pyqtSlot(result=bool)
    def paste(self):
        if not self.canPaste:
            return False
        self._menu_target.forceActiveFocus()
        QMetaObject.invokeMethod(self._menu_target, 'paste', Qt.DirectConnection)
        return True

    @pyqtSlot(bool)
    def setMenuVisible(self, visible):
        self._menu_visible = visible
        self._raw_touch = False
        self._cancel()
        if not visible:
            self._menu_target = None
        self.menuVisibleChanged.emit()

    @pyqtSlot(QObject)
    def showForItem(self, item):
        if item is not None and not sip.isdeleted(item):
            point = item.mapToGlobal(QPointF(0, item.height()))
            self._request(item, point)

    def eventFilter(self, watched, event):
        if not isinstance(watched, QWindow) or self._menu_visible:
            return False
        kind = event.type()
        if kind == QEvent.TouchCancel:
            self._raw_touch = False
            self._cancel()
        elif kind in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd):
            if kind == QEvent.TouchBegin:
                self._raw_touch = True
            elif kind == QEvent.TouchEnd:
                self._raw_touch = False
            points = event.touchPoints()
            if len(points) != 1:
                self._cancel()
                return False
            point = points[0]
            if kind == QEvent.TouchBegin:
                self._press(watched, point.pos(), point.screenPos())
            elif kind == QEvent.TouchEnd:
                self._release(point.screenPos())
            else:
                self._move(point.screenPos())
        elif not self._raw_touch:
            if kind in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
                if event.button() in (Qt.LeftButton, Qt.RightButton):
                    self._press(watched, event.localPos(), event.screenPos())
                    if event.button() == Qt.RightButton:
                        self._timer.stop()
            elif kind == QEvent.MouseMove:
                self._move(event.screenPos())
            elif kind == QEvent.MouseButtonRelease:
                if event.button() in (Qt.LeftButton, Qt.RightButton):
                    self._release(event.screenPos(), event.button() == Qt.RightButton)
        return False

    def _press(self, window, local, screen):
        self._cancel()
        if not isinstance(window, QQuickWindow):
            return
        target = self._find(window.contentItem(), local)
        if target is None or target is _BLOCKED:
            return
        self._target = target
        self._pressed = True
        self._held = False
        self._origin = QPointF(screen)
        self._selection = self._selection_range(target)
        self._timer.start()

    def _move(self, point):
        delta = point - self._origin
        distance = QGuiApplication.styleHints().startDragDistance()
        if delta.x() ** 2 + delta.y() ** 2 > distance ** 2:
            self._timer.stop()

    def _release(self, point, right=False):
        self._timer.stop()
        if not self._pressed:
            return
        self._pressed = False
        item = self._target
        old_selection = self._selection
        if self._held:
            return
        # La seleccion nativa termina de actualizarse despues del filtro.
        def finished():
            if item is None or sip.isdeleted(item) or self._menu_visible:
                return
            selected = item.property('selectedText')
            if right or (selected and self._selection_range(item) != old_selection):
                self._request(item, point)
        QTimer.singleShot(0, finished)

    def _hold(self):
        if self._pressed:
            self._held = True
            self._request(self._target, self._origin)

    def _cancel(self):
        self._timer.stop()
        self._pressed = False
        self._held = False
        self._target = None

    def _request(self, item, point):
        if item is None or sip.isdeleted(item) or not item.isVisible():
            return
        echo = item.property('echoMode')
        text = '' if echo is not None and echo != 0 else (
            item.property('selectedText') or item.property('text') or '')
        if isinstance(text, str) and (text or (self._is_editor(item) and not item.property('readOnly'))):
            self._menu_target = item
            self.menuVisibleChanged.emit()
            self.requested.emit(text, point.x(), point.y())

    @staticmethod
    def _selection_range(item):
        return item.property('selectionStart'), item.property('selectionEnd')

    @staticmethod
    def _is_editor(item):
        return item.property('cursorPosition') is not None and item.property('readOnly') is not None

    def _find(self, item, local):
        if item.property('allowsTextCopy') is False:
            return _BLOCKED
        children = sorted(enumerate(item.childItems()), key=lambda pair: (pair[1].z(), pair[0]), reverse=True)
        for _, child in children:
            if not child.isVisible() or not child.isEnabled():
                continue
            position = child.mapFromItem(item, local)
            if not child.contains(position):
                continue
            found = self._find(child, position)
            if found is not None:
                if found is not _BLOCKED and self._is_editor(item) and not self._is_editor(found):
                    return item
                return found
        text = item.property('text')
        return item if self._is_editor(item) or (isinstance(text, str) and text) else None
