"""Contratos A1: dominio estable, idiomas por instancia y guardado transaccional."""
import ast
import csv
import json
from datetime import datetime
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.qt_support import qt_app
from tests.fakes import FakeRunner
from mulita.adapters.settings_store import JsonSettingsStore, MemorySettingsStore
from mulita.config import AppConfig, Binaries
from mulita.core.commands import CommandFactory
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.messages import Message, message
from mulita.core.models import WifiLink
from mulita.core.settings import Language, Settings
from mulita.core.validation import static_ethernet
from mulita.presentation.facts import wifi_facts
from mulita.presentation.i18n import Translator, pack
from mulita.core.tls import TlsFinding
from mulita.presentation.tls import grouped
from mulita.services.settings import SettingsService
from mulita.services.wifi import WifiService
from mulita.ui.qt.bridge.base import BridgeContext, Notifier
from mulita.ui.qt.bridge.system import I18nController, SettingsController
from mulita.ui.qt.bridge.wifi import WifiController


def settings(language='es', store=None):
    return SettingsService(store or MemorySettingsStore(Settings(language=Language(language))),
                           SimpleNamespace(apply=lambda _: None, available=lambda: False))


def context(service):
    return BridgeContext(AppConfig(test_mode=True), getattr(SimpleNamespace(settings=service), 'settings', None), None, Notifier())


class LocalizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app()

    def test_controllers_and_catalogs_are_independent_between_instances(self):
        spanish, english = settings('es'), settings('en')
        first, second = WifiController(context(spanish), None), WifiController(context(english), None)
        first._link = second._link = WifiLink(ssid='Office')
        first_catalog = I18nController(context(spanish))
        second_catalog = I18nController(context(english))
        self.assertEqual(json.loads(first.linkJson)[0]['label'], 'Red')
        self.assertEqual(json.loads(second.linkJson)[0]['label'], 'Network')
        english.set_language('es')
        spanish.set_language('en')
        self.assertEqual(json.loads(first.linkJson)[0]['label'], 'Network')
        self.assertEqual(json.loads(second.linkJson)[0]['label'], 'Red')
        self.assertEqual(first_catalog.pack['trace'], 'Trace')
        self.assertEqual(second_catalog.pack['trace'], 'Trazar')

    def test_failed_save_does_not_change_language_catalog_or_notify_listeners(self):
        with tempfile.TemporaryDirectory() as folder:
            store = JsonSettingsStore(Path(folder) / 'settings.json')
            store.save(Settings(language=Language.ES))
            service = settings(store=store)
            ctx = context(service)
            controller = SettingsController(ctx)
            catalog = I18nController(ctx)
            notifications, changes = [], []
            ctx.notifier.notified.connect(lambda *args: notifications.append(args))
            service.subscribe(changes.append)
            with patch('mulita.adapters.settings_store.os.replace', side_effect=OSError('read only')):
                controller.setLanguage('en')
            self.assertEqual(service.current.language, Language.ES)
            self.assertEqual(store.load().language, Language.ES)
            self.assertEqual(catalog.language, 'es')
            self.assertEqual(catalog.pack['trace'], 'Trazar')
            self.assertEqual(changes, [])
            self.assertEqual(notifications[0][0], 'error')
            self.assertEqual(notifications[0][2], Translator('es').tr('settingsSaveFailed'))
            self.assertFalse(store._path.with_suffix('.tmp').exists())

    def test_successful_save_precedes_notification(self):
        with tempfile.TemporaryDirectory() as folder:
            store = JsonSettingsStore(Path(folder) / 'settings.json')
            service = settings(store=store)
            observed = []
            service.subscribe(lambda value: observed.append((value.language, store.load().language)))
            service.set_language('en')
            self.assertEqual(observed, [(Language.EN, Language.EN)])

    def test_domain_errors_keep_codes_and_nested_parameters(self):
        with self.assertRaises(ValidationError) as caught:
            static_ethernet('invalid', '24')
        error = caught.exception
        self.assertEqual(error.code, 'badIp')
        self.assertIsInstance(error.parameters['field'], Message)
        self.assertEqual(error.parameters['field'].code, 'fieldAddress')
        self.assertEqual(error.parameters['value'], 'invalid')
        es, en = Translator('es'), Translator('en')
        self.assertNotEqual(es.render(error), en.render(error))
        self.assertIn('invalid', en.render(error))
        self.assertNotIn('fieldAddress', en.render(error))

    def test_command_failure_keeps_translatable_cause_and_raw_detail(self):
        error = CommandFailedError(message('commandFailure', message=message('wifiForgetFailed'),
                                           detail='permission denied'))
        rendered = Translator('en').render(error)
        self.assertEqual(rendered, 'Could not forget the network: permission denied')

    def test_raw_values_are_not_interpreted_as_translation_keys(self):
        translator = Translator('en')
        self.assertEqual(translator.render('factSsid'), 'factSsid')
        link = WifiLink(ssid='factSsid')
        self.assertEqual(link.facts(), [('ssid', 'factSsid')])
        self.assertEqual(wifi_facts(link, translator), [('Network', 'factSsid')])

    def test_serialized_notes_are_localized_without_modifying_domain_messages(self):
        note = message('nmapPnWarn')
        english = WifiController(context(settings('en')), None)
        spanish = WifiController(context(settings('es')), None)
        self.assertEqual(json.loads(english._json([note])), [Translator('en').tr('nmapPnWarn')])
        self.assertEqual(json.loads(spanish._json([note])), [Translator('es').tr('nmapPnWarn')])
        self.assertEqual(str(note), 'nmapPnWarn')

    def test_tls_presenters_use_explicit_locales_and_preserve_findings(self):
        finding = TlsFinding('cert_commonName', 'OK', 'Office', 'certificate')
        es = grouped((finding,), Translator('es'))
        en = grouped((finding,), Translator('en'))
        self.assertEqual(es[0]['title'], 'Certificado')
        self.assertEqual(en[0]['title'], 'Certificate')
        self.assertEqual(es[1]['test'], 'Nombre común (CN)')
        self.assertEqual(en[1]['test'], 'Common name (CN)')
        self.assertEqual(finding, TlsFinding('cert_commonName', 'OK', 'Office', 'certificate'))

    def test_export_schema_and_values_do_not_depend_on_any_ui_language(self):
        link = WifiLink(ssid='Office', mode='managed', address='192.0.2.10')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first, second = root / 'one', root / 'two'
            first.mkdir()
            second.mkdir()
            runner, commands = FakeRunner(), CommandFactory(Binaries())
            moment = datetime(2026, 11, 1, 10, 0)
            settings('es')
            a = WifiService(runner, commands, first).save(link, moment)
            settings('en')
            b = WifiService(runner, commands, second).save(link, moment)
            self.assertEqual((first / a).read_bytes(), (second / b).read_bytes())
            with (first / a).open(encoding='utf-8', newline='') as handle:
                self.assertEqual(list(csv.reader(handle)), [
                    ['ssid', 'Office'], ['mode', 'managed'], ['address', '192.0.2.10']])
            self.assertNotEqual(wifi_facts(link, Translator('es')), wifi_facts(link, Translator('en')))

    def test_message_parameters_and_returned_catalog_cannot_mutate_other_instances(self):
        token = message('badIp', value='bad')
        with self.assertRaises(TypeError):
            token.parameters['value'] = 'changed'
        catalog = pack('en')
        catalog['trace'] = 'modified'
        self.assertEqual(pack('en')['trace'], 'Trace')

    def test_core_and_services_do_not_import_presentation_or_toolkits(self):
        root = Path(__file__).resolve().parents[1] / 'mulita'
        violations = []
        for folder in ('core', 'services'):
            for path in (root / folder).glob('*.py'):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    imports = ([node.module or ''] if isinstance(node, ast.ImportFrom)
                               else [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
                    for module in imports:
                        if module.startswith(('mulita.presentation', 'mulita.ui', 'PyQt5')):
                            violations.append(f'{path.name}:{node.lineno}:{module}')
        self.assertEqual(violations, [])
