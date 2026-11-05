"""Diagnostic categories shared by recording policy and settings."""
TESTS = (
    ('trace', 'tracesTitle'), ('ping', 'pingTitle'), ('capture', 'captureTitle'),
    ('ports', 'scanPorts'), ('discovery', 'discoverTitle'), ('switch', 'switchTitle'),
    ('tap', 'homeTap'), ('wol', 'toolWol'), ('climate', 'toolClimate'),
    ('speed', 'toolSpeed'), ('public_ip', 'publicIp'), ('wifi_info', 'wifiInfo'),
    ('vendor', 'vendor'), ('nmap', 'cyberNmap'), ('server', 'pageServers'), ('tls', 'cyberTls'),
)
TEST_IDS = tuple(key for key, _ in TESTS)
PLACES = {'captura': 'capture', 'traza': 'trace', 'ping': 'ping', 'escaneo': 'ports',
          'descubrimiento': 'discovery', 'puerto-switch': 'switch', 'tap': 'tap',
          'publica': 'public_ip', 'wifi': 'wifi_info', 'nmap': 'nmap',
          'servidores': 'server', 'tls': 'tls'}


def enabled_tests(value):
    if not isinstance(value, dict):
        return TEST_IDS
    return tuple(key for key in TEST_IDS if value.get(key) is not False)


def category(event):
    if event.action in TEST_IDS:
        return event.action
    if event.action == 'tap_stop':
        return 'tap'
    if event.action == 'ping_export':
        return 'ping'
    if event.action in ('export', 'web_export'):
        test = event.parameters.test or PLACES.get(event.parameters.place)
        return test if test in TEST_IDS else None
    return None
