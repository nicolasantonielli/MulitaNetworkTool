import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from tests.qt_support import qt_app
from mulita.core.models import EthernetConfig
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.ipv4 import IPv4Controller
from mulita.ui.qt.bridge.ethernet import InternalEthernetController


class IPv4ControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def context(self):
        dispatcher = SimpleNamespace(background=lambda task, ok, fail: ok(task()))
        settings = SimpleNamespace(subscribe=lambda fn: None,
                                   current=SimpleNamespace(language=SimpleNamespace(value='es')))
        return BridgeContext(None, SimpleNamespace(settings=settings), dispatcher, Notifier())

    def test_ipv4_uses_only_shared_contract_and_has_no_vlan_actions(self):
        network = SimpleNamespace(read=Mock(return_value=EthernetConfig()),
                                  apply_dhcp=Mock(return_value=EthernetConfig()),
                                  apply_static=Mock(return_value=EthernetConfig()))
        controller = IPv4Controller(self.context(), network, lambda: 'Wi-Fi', 'wifiIp')
        controller.refresh()
        controller.apply('dhcp', '', '', '', '')
        controller.apply('static', '192.0.2.2', '255.255.255.0', '', '')
        network.read.assert_called_once_with()
        network.apply_dhcp.assert_called_once_with()
        network.apply_static.assert_called_once_with('192.0.2.2', '255.255.255.0', '', '')
        self.assertFalse(hasattr(controller, 'applyVlan'))
        self.assertFalse(hasattr(controller, 'vlanId'))

    def test_ethernet_refresh_and_vlan_remain_specific(self):
        network = SimpleNamespace(interface='eth0.20', vlan_id=20,
                                  read_with_vlan=Mock(return_value=EthernetConfig()),
                                  apply_with_vlan=Mock(return_value=EthernetConfig()))
        controller = InternalEthernetController(self.context(), network)
        controller.refresh()
        controller.applyVlan('dhcp', '', '', '', '', True, '20')
        network.read_with_vlan.assert_called_once_with()
        network.apply_with_vlan.assert_called_once_with('dhcp', '', '', '', '', True, '20')
        self.assertEqual(controller.interfaceName, 'eth0.20')
        self.assertEqual(controller.vlanId, 20)
