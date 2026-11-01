import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from tests.qt_support import qt_app
from mulita.ui.qt.app import QtApplication

from mulita.ui.qt.touch_debug import real_mouse_names

DEVICES = '''
N: Name="10-0038 generic ft5x06 (80)"
H: Handlers=mouse0 event0

N: Name="vc4-hdmi-0"
H: Handlers=kbd event1

N: Name="Logitech USB Optical Mouse"
H: Handlers=mouse1 event5
'''


class RealMouseTest(unittest.TestCase):

    def test_direct_input_panel_is_not_mouse_even_with_generic_name(self):
        text = 'N: Name="USB Input Device"\nH: Handlers=mouse0 event0\nB: PROP=2\nB: REL=3\n'
        self.assertEqual(real_mouse_names(text), [])

    def test_absolute_panel_is_not_mouse(self):
        text = 'N: Name="USB Input Device"\nH: Handlers=mouse0 event0\nB: EV=b\nB: ABS=3\n'
        self.assertEqual(real_mouse_names(text), [])

    def test_relative_usb_mouse_is_detected(self):
        text = 'N: Name="USB Input Device"\nH: Handlers=mouse0 event0\nB: EV=17\nB: REL=103\nB: PROP=0\n'
        self.assertEqual(real_mouse_names(text), ['USB Input Device'])

    def test_goodix_panel_is_ignored(self):
        text = 'N: Name="Goodix Capacitive TouchScreen"\nH: Handlers=mouse0 event0\n'
        self.assertEqual(real_mouse_names(text), [])

    def test_ignores_the_touch_panel(self):
        self.assertEqual(real_mouse_names(DEVICES), ['Logitech USB Optical Mouse'])

    def test_panel_alone_is_not_a_mouse(self):
        text = 'N: Name="10-0038 generic ft5x06 (80)"\nH: Handlers=mouse0 event0\n'
        self.assertEqual(real_mouse_names(text), [])


class CursorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def setUp(self):
        self.controller = QtApplication.__new__(QtApplication)
        self.controller.app = self.app
        self.controller._pointer_cursor = False
        self.app.setOverrideCursor(QCursor(Qt.BlankCursor))
        self.addCleanup(self.app.restoreOverrideCursor)

    def test_mouse_connection_and_removal_updates_cursor(self):
        with patch('mulita.ui.qt.touch_debug.connected_mice', return_value=['USB Mouse']):
            self.controller._sync_cursor()
        self.assertEqual(self.app.overrideCursor().shape(), Qt.ArrowCursor)
        with patch('mulita.ui.qt.touch_debug.connected_mice', return_value=[]):
            self.controller._sync_cursor()
        self.assertEqual(self.app.overrideCursor().shape(), Qt.BlankCursor)

    def test_cursor_is_hidden_again_if_another_control_changed_it(self):
        self.app.changeOverrideCursor(QCursor(Qt.ArrowCursor))
        with patch('mulita.ui.qt.touch_debug.connected_mice', return_value=[]):
            self.controller._sync_cursor()
        self.assertEqual(self.app.overrideCursor().shape(), Qt.BlankCursor)
