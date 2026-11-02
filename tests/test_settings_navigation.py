import os
import unittest
from unittest.mock import Mock

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'

from PyQt5.QtCore import QObject
from PyQt5.QtQml import QQmlExpression, QQmlEngine
from mulita.adapters.settings_store import MemorySettingsStore
from mulita.bootstrap import build_services
from mulita.config import AppConfig
from mulita.core.models import CommandResult, EthernetConfig
from mulita.ui.qt.app import QtApplication
from tests.fakes import FakeRunner


class SettingsNavigationTest(unittest.TestCase):
    def test_descriptors_control_menu_component_and_returns_after_reordering(self):
        config = AppConfig(test_mode=True)
        services = build_services(config, runner=FakeRunner({'/usr/bin/ip': CommandResult(0, '[]'), '/usr/bin/nmcli': CommandResult(0, '')}),
                                  settings_store=MemorySettingsStore())
        services.ethernet.read_with_vlan = Mock(return_value=EthernetConfig())
        app = QtApplication(config, services)
        try:
            root = app.root.findChild(QObject, 'settingsPage')
            self.assertIsNotNone(root)
            context = QQmlEngine.contextForObject(root.findChild(QObject, 'settingsStack'))

            def evaluate(script):
                expression = QQmlExpression(context, root, script)
                value = expression.evaluate()
                self.assertFalse(expression.hasError(), expression.error().toString())
                app.app.processEvents()
                return value

            def check(page):
                self.assertEqual(root.property('currentPage'), page)
                loader = evaluate('pageRepeater.itemAt(pageIndex(currentPage))')[0]
                self.assertIsNotNone(loader)
                self.assertEqual(loader.property('item').objectName(), page)
                stack = root.findChild(QObject, 'settingsStack')
                expected = evaluate('pageIndex(currentPage)')[0]
                self.assertEqual(stack.property('currentIndex'), expected)

            for reordered in (False, True):
                if reordered:
                    evaluate('pages = pages.slice().reverse()')
                for page in ('general', 'display', 'wifi', 'ethernet', 'maintenance', 'interface', 'touch', 'tiles'):
                    evaluate('navigate("' + page + '")')
                    check(page)
                evaluate('navigate(menuPages[0].id)')
                for index in range(6):
                    nav = root.findChild(QObject, 'settingsNav')
                    nav.setProperty('currentIndex', index)
                    check(evaluate('menuPages[' + str(index) + '].id')[0])
                for page, back in [('touch', 'display'), ('tiles', 'interface')]:
                    evaluate('navigate("' + page + '")')
                    evaluate('pageRepeater.itemAt(pageIndex(currentPage)).item.goBack()')
                    check(back)
            evaluate('navigate("unknown")')
            check('interface')
            loader = evaluate('pageRepeater.itemAt(pageIndex(currentPage))')[0]
            services.settings.set_language('en')
            app.app.processEvents()
            self.assertIs(evaluate('pageRepeater.itemAt(pageIndex(currentPage))')[0], loader)
            check('interface')
        finally:
            app.dispose()
