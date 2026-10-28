import http.client
import io
import os
import shutil
import socket
import ssl
import struct
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock

from mulita.servers import ntp, tftp, web


def free_udp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def tftp_request(opcode, name, port, mode='octet'):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)
    sock.sendto(struct.pack('!H', opcode) + name.encode() + b'\0' + mode.encode() + b'\0',
                ('127.0.0.1', port))
    return sock


def tftp_get(port, name):
    sock = tftp_request(tftp.RRQ, name, port)
    data = b''
    try:
        while True:
            packet, peer = sock.recvfrom(600)
            opcode, number = struct.unpack('!HH', packet[:4])
            if opcode == tftp.ERROR:
                return ('error', number, packet[4:-1].decode())
            data += packet[4:]
            sock.sendto(struct.pack('!HH', tftp.ACK, number), peer)
            if len(packet) - 4 < tftp.BLOCK:
                return ('ok', data)
    finally:
        sock.close()


def tftp_put(port, name, content):
    sock = tftp_request(tftp.WRQ, name, port)
    try:
        packet, peer = sock.recvfrom(600)
        opcode, number = struct.unpack('!HH', packet[:4])
        if opcode == tftp.ERROR:
            return ('error', number, packet[4:-1].decode())
        blocks = [content[i:i + tftp.BLOCK] for i in range(0, len(content), tftp.BLOCK)]
        if not blocks or len(blocks[-1]) == tftp.BLOCK:
            blocks.append(b'')
        for index, chunk in enumerate(blocks, start=1):
            sock.sendto(struct.pack('!HH', tftp.DATA, index) + chunk, peer)
            reply, _ = sock.recvfrom(600)
            assert struct.unpack('!HH', reply[:4]) == (tftp.ACK, index)
        return ('ok',)
    finally:
        sock.close()


class TftpTest(unittest.TestCase):

    def start(self, writable=True):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, 'tftp')
        os.makedirs(self.root)
        self.port = free_udp_port()
        patcher = mock.patch('sys.stdout', io.StringIO())
        self.output = patcher.start()
        self.addCleanup(patcher.stop)
        ready, self.stop = threading.Event(), threading.Event()
        thread = threading.Thread(target=tftp.serve, args=(
            '127.0.0.1', self.port, self.root, writable, ready, self.stop), daemon=True)
        thread.start()
        self.assertTrue(ready.wait(3))
        self.addCleanup(lambda: (self.stop.set(), thread.join(2)))

    def test_downloads_small_exact_multiple_and_large_files(self):
        self.start()
        for name, size in (('small.bin', 10), ('exact.bin', 1024), ('large.bin', 512 * 40 + 7), ('empty.bin', 0)):
            content = os.urandom(size)
            with open(os.path.join(self.root, name), 'wb') as handle:
                handle.write(content)
            self.assertEqual(tftp_get(self.port, name), ('ok', content), name)

    def test_uploads_are_stored_and_logged(self):
        self.start()
        content = os.urandom(512 * 3)
        self.assertEqual(tftp_put(self.port, 'sw1.cfg', content), ('ok',))
        time.sleep(0.2)
        with open(os.path.join(self.root, 'sw1.cfg'), 'rb') as handle:
            self.assertEqual(handle.read(), content)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'sw1.cfg.part')))
        self.assertIn('127.0.0.1\tRecibido sw1.cfg (1536 bytes)', self.output.getvalue())

    def test_upload_replaces_an_existing_file(self):
        self.start()
        with open(os.path.join(self.root, 'run.cfg'), 'wb') as handle:
            handle.write(b'viejo')
        self.assertEqual(tftp_put(self.port, 'run.cfg', b'nuevo'), ('ok',))
        time.sleep(0.2)
        with open(os.path.join(self.root, 'run.cfg'), 'rb') as handle:
            self.assertEqual(handle.read(), b'nuevo')

    def test_uploads_can_be_disabled(self):
        self.start(writable=False)
        self.assertEqual(tftp_put(self.port, 'x.cfg', b'datos')[:2], ('error', 2))
        self.assertFalse(os.path.exists(os.path.join(self.root, 'x.cfg')))

    def test_missing_file_and_escapes_are_refused(self):
        self.start()
        secret = os.path.join(self.tmp.name, 'secreto.txt')
        with open(secret, 'w') as handle:
            handle.write('no')
        self.assertEqual(tftp_get(self.port, 'nada.bin')[:2], ('error', 1))
        for name in ('../secreto.txt', '..\\secreto.txt', '/etc/passwd', '..'):
            self.assertEqual(tftp_get(self.port, name)[:2][0], 'error', name)
        self.assertEqual(tftp_put(self.port, '../escape.cfg', b'x')[:2], ('error', 2))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, 'escape.cfg')))

    def test_resolve_stays_inside_the_root(self):
        root = os.path.realpath(self.tmp_dir())
        self.assertEqual(tftp.resolve(root, 'a/b.cfg'), os.path.join(root, 'a', 'b.cfg'))
        self.assertIsNone(tftp.resolve(root, '../x'))
        self.assertIsNone(tftp.resolve(root, ''))

    def tmp_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name

    def test_malformed_and_unknown_requests_do_not_stop_the_server(self):
        self.start()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        sock.sendto(b'\x00', ('127.0.0.1', self.port))
        sock.sendto(b'\x00\x09basura\x00', ('127.0.0.1', self.port))
        sock.close()
        content = b'sigue vivo'
        with open(os.path.join(self.root, 'ok.bin'), 'wb') as handle:
            handle.write(content)
        self.assertEqual(tftp_get(self.port, 'ok.bin'), ('ok', content))

    def test_port_in_use_exits_with_a_message(self):
        holder = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        holder.bind(('127.0.0.1', 0))
        self.addCleanup(holder.close)
        with mock.patch('sys.stdout', io.StringIO()) as output:
            with self.assertRaises(SystemExit):
                tftp.serve('127.0.0.1', holder.getsockname()[1], self.tmp_dir(), True)
        self.assertIn('No se pudo abrir el puerto', output.getvalue())


class NtpTest(unittest.TestCase):

    def request(self, version=4, mode=3, transmit=b'\x01\x02\x03\x04\x05\x06\x07\x08'):
        packet = bytearray(48)
        packet[0] = (version << 3) | mode
        packet[40:48] = transmit
        return bytes(packet)

    def test_reply_echoes_the_client_timestamp_and_announces_a_server(self):
        now = 1_700_000_000.25
        reply = ntp.build_reply(self.request(), now, 3, transmit=now + 0.001)
        self.assertEqual(len(reply), 48)
        self.assertEqual(reply[0], (4 << 3) | 4)
        self.assertEqual(reply[1], 3)
        self.assertEqual(reply[24:32], b'\x01\x02\x03\x04\x05\x06\x07\x08')
        seconds = struct.unpack('!I', reply[40:44])[0] - ntp.NTP_EPOCH
        self.assertEqual(seconds, 1_700_000_000)

    def test_keeps_the_client_version_and_ignores_other_modes(self):
        self.assertEqual(ntp.build_reply(self.request(version=3), 1.0, 2)[0] >> 3 & 7, 3)
        self.assertIsNone(ntp.build_reply(self.request(mode=4), 1.0, 2))
        self.assertIsNone(ntp.build_reply(b'corto', 1.0, 2))

    def test_serves_over_udp_and_logs_the_client(self):
        port = free_udp_port()
        ready, stop = threading.Event(), threading.Event()
        with mock.patch('sys.stdout', io.StringIO()) as output:
            thread = threading.Thread(target=ntp.serve, args=('127.0.0.1', port, 2, ready, stop), daemon=True)
            thread.start()
            self.assertTrue(ready.wait(3))
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(3)
            client.sendto(self.request(), ('127.0.0.1', port))
            reply, _ = client.recvfrom(100)
            client.close()
            stop.set()
            thread.join(2)
        self.assertEqual(len(reply), 48)
        sent = struct.unpack('!I', reply[40:44])[0] - ntp.NTP_EPOCH
        self.assertLess(abs(sent - time.time()), 5)
        self.assertIn('127.0.0.1\tHora entregada (NTPv4)', output.getvalue())


class WebTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, 'web')
        self.captures = os.path.join(self.tmp.name, 'capturas')
        os.makedirs(self.root)
        os.makedirs(self.captures)
        with open(os.path.join(self.root, 'firmware.bin'), 'wb') as handle:
            handle.write(b'FW' * 100)
        with open(os.path.join(self.captures, 'informe.csv'), 'wb') as handle:
            handle.write(b'a,b\n')
        with open(os.path.join(self.tmp.name, 'privado.txt'), 'w') as handle:
            handle.write('no')
        patcher = mock.patch('sys.stdout', io.StringIO())
        self.output = patcher.start()
        self.addCleanup(patcher.stop)

    def serve(self, captures=True, context=None, handler=None):
        server = web.Server(('127.0.0.1', 0), handler or web.Handler, self.root,
                            self.captures if captures else '', context)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(2)))
        return server.server_address[1]

    def get(self, port, path, method='GET'):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read()
        connection.close()
        return response.status, body

    def test_home_page_confirms_connectivity_and_shows_the_client(self):
        port = self.serve()
        status, body = self.get(port, '/')
        self.assertEqual(status, 200)
        text = body.decode()
        self.assertIn('Conexion establecida', text)
        self.assertIn('127.0.0.1', text)
        self.assertIn('/capturas/', text)
        self.assertEqual(self.get(port, '/', 'HEAD')[1], b'')

    def test_files_are_served_from_the_root_and_from_archivos(self):
        port = self.serve()
        self.assertEqual(self.get(port, '/firmware.bin'), (200, b'FW' * 100))
        self.assertEqual(self.get(port, '/archivos/firmware.bin'), (200, b'FW' * 100))
        self.assertEqual(self.get(port, '/nada.bin')[0], 404)
        self.assertEqual(self.get(port, '/archivos/')[0], 200)

    def test_captures_are_shared_only_when_enabled(self):
        self.assertEqual(self.get(self.serve(captures=True), '/capturas/informe.csv'), (200, b'a,b\n'))
        status, body = self.get(self.serve(captures=False), '/capturas/')
        self.assertEqual(status, 404)
        self.assertNotIn(b'informe', body)

    def test_paths_cannot_escape_the_folders(self):
        port = self.serve()
        for path in ('/../privado.txt', '/%2e%2e/privado.txt', '/capturas/../privado.txt',
                     '/archivos/../../privado.txt', '/..%2fprivado.txt'):
            status, body = self.get(port, path)
            self.assertNotEqual(body, b'no', path)
            self.assertIn(status, (200, 404), path)

    def test_test_downloads_have_the_requested_size(self):
        port = self.serve()
        status, body = self.get(port, '/prueba/2')
        self.assertEqual((status, len(body)), (200, 2 * 1024 * 1024))
        self.assertEqual(web.test_size('/prueba/5000'), web.MAX_TEST_MB * 1024 * 1024)
        self.assertIsNone(web.test_size('/prueba/abc'))
        self.assertIsNone(web.test_size('/prueba'))

    def test_requests_are_logged_with_client_and_status(self):
        port = self.serve()
        self.get(port, '/firmware.bin')
        self.get(port, '/nada.bin')
        time.sleep(0.1)
        lines = self.output.getvalue()
        self.assertIn('127.0.0.1\tGET /firmware.bin 200', lines)
        self.assertIn('127.0.0.1\tGET /nada.bin 404', lines)

    def test_map_path_rules(self):
        self.assertEqual(web.map_path('/archivos/a/b.txt', 'R', 'C'), os.path.join('R', 'a', 'b.txt'))
        self.assertEqual(web.map_path('/capturas/x.csv', 'R', 'C'), os.path.join('C', 'x.csv'))
        self.assertEqual(web.map_path('/capturas/x.csv', 'R', ''), os.path.join('R', 'capturas', 'x.csv'))
        self.assertEqual(web.map_path('/../../etc/passwd', 'R', 'C'), os.path.join('R', 'etc', 'passwd'))

    @unittest.skipUnless(shutil.which('openssl'), 'requiere openssl')
    def test_https_serves_the_same_page(self):
        certificate, key = os.path.join(self.tmp.name, 'c.pem'), os.path.join(self.tmp.name, 'k.pem')
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '2',
                        '-subj', '/CN=mulita', '-keyout', key, '-out', certificate],
                       check=True, capture_output=True)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, key)
        port = self.serve(context=context, handler=web.SecureHandler)
        client = ssl.create_default_context()
        client.check_hostname = False
        client.verify_mode = ssl.CERT_NONE
        connection = http.client.HTTPSConnection('127.0.0.1', port, timeout=5, context=client)
        connection.request('GET', '/')
        response = connection.getresponse()
        text = response.read().decode()
        connection.close()
        self.assertEqual(response.status, 200)
        self.assertIn('por HTTPS', text)

    @unittest.skipUnless(shutil.which('openssl'), 'requiere openssl')
    def test_a_client_that_does_not_speak_tls_does_not_block_the_server(self):
        certificate, key = os.path.join(self.tmp.name, 'c.pem'), os.path.join(self.tmp.name, 'k.pem')
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '2',
                        '-subj', '/CN=mulita', '-keyout', key, '-out', certificate],
                       check=True, capture_output=True)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, key)
        port = self.serve(context=context, handler=web.SecureHandler)
        plain = socket.create_connection(('127.0.0.1', port), timeout=3)
        plain.sendall(b'GET / HTTP/1.0\r\n\r\n')
        client = ssl.create_default_context()
        client.check_hostname = False
        client.verify_mode = ssl.CERT_NONE
        connection = http.client.HTTPSConnection('127.0.0.1', port, timeout=5, context=client)
        connection.request('GET', '/')
        self.assertEqual(connection.getresponse().status, 200)
        connection.close()
        plain.close()
        time.sleep(0.2)
        self.assertIn('Conexion fallida', self.output.getvalue())


class ProcessTest(unittest.TestCase):
    """Los comandos que arma Mulita arrancan de verdad como procesos aparte."""

    def run_command(self, argv, ready_text):
        from mulita.adapters.subprocess_runner import SubprocessCommandRunner
        lines, done = [], threading.Event()

        def output(text):
            lines.append(text)
            if ready_text in text:
                done.set()

        handle = SubprocessCommandRunner().start(argv, on_output=output)
        self.addCleanup(handle.terminate)
        self.assertTrue(done.wait(10), ''.join(lines))
        return handle, lines

    def test_ntp_command_answers_and_logs_a_line_the_log_can_read(self):
        from mulita.config import Binaries
        from mulita.core.commands import CommandFactory
        from mulita.core.servers import ServerLog, kind_by_id
        port = free_udp_port()
        handle, lines = self.run_command(
            CommandFactory(Binaries()).ntp_server(port, 2, '127.0.0.1'), 'escuchando')
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(3)
        request = bytearray(48)
        request[0] = 0x23
        client.sendto(bytes(request), ('127.0.0.1', port))
        self.assertEqual(len(client.recvfrom(100)[0]), 48)
        client.close()
        deadline = time.time() + 3
        while not any('Hora entregada' in line for line in lines) and time.time() < deadline:
            time.sleep(0.05)
        log = ServerLog(kind_by_id('ntp'))
        log.feed(''.join(lines))
        self.assertEqual(log.rows[-1]['client'], '127.0.0.1')
        handle.terminate()

    def test_tftp_and_web_commands_start_and_report_their_port(self):
        from mulita.config import Binaries
        from mulita.core.commands import CommandFactory
        commands = CommandFactory(Binaries())
        with tempfile.TemporaryDirectory() as folder:
            self.run_command(commands.tftp_server(folder, free_udp_port(), '127.0.0.1'), 'TFTP escuchando')
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                http_port = probe.getsockname()[1]
            self.run_command(commands.web_server(folder, http_port, 0, '127.0.0.1'), 'HTTP escuchando')

    def test_a_busy_port_ends_the_process_with_the_reason(self):
        from mulita.config import Binaries
        from mulita.core.commands import CommandFactory
        holder = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        holder.bind(('127.0.0.1', 0))
        self.addCleanup(holder.close)
        _handle, lines = self.run_command(
            CommandFactory(Binaries()).ntp_server(holder.getsockname()[1], 3, '127.0.0.1'),
            'No se pudo abrir el puerto')
        self.assertTrue(any('No se pudo abrir' in line for line in lines))


if __name__ == '__main__':
    unittest.main()
