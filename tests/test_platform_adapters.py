import ast
import socket
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from mulita.adapters.switchport import LinuxPacketSource
from mulita.core.errors import CommandFailedError
from mulita.core.platform import ReceivedFrame


class PacketAdapterTest(unittest.TestCase):
    def source(self, receiver):
        api = SimpleNamespace(AF_PACKET=17, SOCK_RAW=3, htons=socket.htons,
                              if_nametoindex=lambda _: 2, socket=lambda *args: receiver)
        return LinuxPacketSource(api)

    def test_auxdata_outgoing_timeout_and_socket_cleanup(self):
        class Socket:
            def __enter__(self): return self
            def __exit__(self, *args): self.closed = True
            bind = Mock()
            settimeout = Mock()
            setsockopt = Mock()
            closed = False
            recvmsg = Mock(side_effect=[
                (b'frame', [(263, 8, struct.pack('IIIHHHH', 1 << 4, 0, 0, 0, 0, 55, 0x8100))],
                 0, ('eth0', 0, 0)),
                (b'outgoing', [], 0, ('eth0', 0, 4)),
                socket.timeout(),
            ])
        receiver = Socket()
        with self.source(receiver).open('eth0') as packets:
            self.assertEqual(packets.receive(), ReceivedFrame(b'frame', (55,)))
            self.assertIsNone(packets.receive())
            self.assertIsNone(packets.receive())
        self.assertTrue(receiver.closed)
        receiver.bind.assert_called_once_with(('eth0', 0))
        receiver.settimeout.assert_called_once_with(0.25)
        self.assertEqual(receiver.setsockopt.call_count, 2)

    def test_permission_and_receive_errors_are_normalized_and_close_socket(self):
        for error, code in ((PermissionError('denied'), 'switchPermission'),
                            (OSError('disconnected'), 'switchFailed')):
            with self.subTest(code=code):
                class Socket:
                    closed = False
                    def __enter__(self): return self
                    def __exit__(self, *args): self.closed = True
                    def bind(self, value): pass
                    def settimeout(self, value): pass
                    def setsockopt(self, *args): pass
                    def recvmsg(self, *args): raise error
                receiver = Socket()
                with self.assertRaises(CommandFailedError) as caught:
                    with self.source(receiver).open('eth0') as packets:
                        packets.receive()
                self.assertEqual(caught.exception.code, code)
                self.assertIs(caught.exception.__cause__, error)
                self.assertTrue(receiver.closed)

    def test_unsupported_platform_has_controlled_error(self):
        with self.assertRaises(CommandFailedError) as caught:
            with LinuxPacketSource(SimpleNamespace()).open('eth0'):
                self.fail('must not open')
        self.assertEqual(caught.exception.code, 'switchLinux')


class ServiceBoundariesTest(unittest.TestCase):
    def test_controllers_cannot_reach_global_service_container(self):
        from dataclasses import fields
        from mulita.ui.qt.bridge.base import BridgeContext
        self.assertEqual({field.name for field in fields(BridgeContext)},
                         {'config', 'settings', 'dispatcher', 'notifier'})
        root = Path(__file__).resolve().parents[1] / 'mulita/ui/qt/bridge'
        for path in root.glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, ('services', '_services'), str(path))

    def test_a3_services_do_not_import_hardware_implementations(self):
        root = Path(__file__).resolve().parents[1] / 'mulita' / 'services'
        for name in ('settings.py', 'switchport.py', 'files.py'):
            tree = ast.parse((root / name).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                modules = ([node.module or ''] if isinstance(node, ast.ImportFrom)
                           else [a.name for a in node.names] if isinstance(node, ast.Import) else [])
                for module in modules:
                    self.assertFalse(module.startswith(('mulita.adapters', 'socket')),
                                     f'{name}:{node.lineno}: {module}')
