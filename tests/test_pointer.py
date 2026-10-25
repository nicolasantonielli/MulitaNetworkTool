import unittest

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

    def test_ignores_the_touch_panel(self):
        self.assertEqual(real_mouse_names(DEVICES), ['Logitech USB Optical Mouse'])

    def test_panel_alone_is_not_a_mouse(self):
        text = 'N: Name="10-0038 generic ft5x06 (80)"\nH: Handlers=mouse0 event0\n'
        self.assertEqual(real_mouse_names(text), [])
