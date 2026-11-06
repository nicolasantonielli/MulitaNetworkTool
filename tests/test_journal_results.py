import unittest
from types import SimpleNamespace

from mulita.core.models import ClimateReading, PingSummary, PortFinding
from mulita.presentation.i18n import Translator
from mulita.presentation.journal import render_event
from mulita.presentation.journal_results import formatted_results
from mulita.services.event_factory import make_event


def completed(action, parameters, result):
    return make_event(action, 'completed', parameters, result)


class FormattedResultsTest(unittest.TestCase):
    def test_other_phases_keep_the_fallback(self):
        event = make_event('ping', 'started', {'target': '8.8.8.8'})
        self.assertEqual(formatted_results(event, 'es', 'respaldo'), 'respaldo')

    def test_ping_lists_fields_and_average(self):
        summary = PingSummary(target='8.8.8.8', transmitted='2', received='1', loss='50%', average='10.0')
        text = formatted_results(completed('ping', {}, {'summary': summary, 'replies': 2}), 'es', '')
        self.assertEqual(text.splitlines()[0], 'Destino: 8.8.8.8')
        self.assertIn('10.0 ms', text)

    def test_incomplete_ping_reports_the_replies_seen(self):
        text = formatted_results(completed('ping', {'target': 'x'}, {'summary': PingSummary(), 'replies': 3}), 'en', '')
        self.assertIn('3', text.splitlines()[1])

    def test_ports_join_service_only_when_known(self):
        findings = (PortFinding('192.0.2.1', '443', 'tcp', 'open', 'https'),
                    PortFinding('192.0.2.1', '22', 'tcp', 'open', ''))
        self.assertEqual(formatted_results(completed('ports', {}, findings), 'es', '').splitlines(),
                         ['192.0.2.1 · 443/tcp · open · https', '192.0.2.1 · 22/tcp · open'])

    def test_empty_payloads_fall_back(self):
        self.assertEqual(formatted_results(completed('climate', {}, None), 'es', 'respaldo'), 'respaldo')
        self.assertEqual(formatted_results(completed('tap', {}, ''), 'es', 'respaldo'), 'respaldo')
        self.assertEqual(formatted_results(completed('nmap', {}, None), 'es', 'respaldo'), 'respaldo')
        self.assertEqual(formatted_results(completed('capture', {}, None), 'es', 'respaldo'), 'respaldo')

    def test_failed_exit_code_marks_partial_results(self):
        event = completed('climate', {'exit_code': 2}, ClimateReading(25, 60))
        first, *rest = formatted_results(event, 'es', '').splitlines()
        self.assertIn('parcial', first.lower())
        self.assertTrue(rest)
        stopped = completed('climate', {'exit_code': 2, 'stopped': True}, ClimateReading(25, 60))
        self.assertNotIn('parcial', formatted_results(stopped, 'es', '').lower())

    def test_nmap_lists_hosts_on_separate_lines(self):
        value = SimpleNamespace(hosts=({'ip': '192.0.2.1'}, {'ip': '192.0.2.2'}), status='ok', open_ports='443')
        text = formatted_results(completed('nmap', {}, value), 'es', '')
        self.assertIn('• 192.0.2.1\n• 192.0.2.2', text)

    def test_switch_without_neighbors_says_so(self):
        value = {'interface': 'eth0', 'cancelled': False, 'frames': 0, 'neighbors': []}
        text = formatted_results(completed('switch', {}, value), 'en', '')
        self.assertIn('eth0', text)
        self.assertEqual(text.splitlines()[-1], Translator('en').tr('journalNoneObserved'))


class RenderEventPhasesTest(unittest.TestCase):
    def test_started_is_quiet_for_exports_and_climate(self):
        for action in ('export', 'climate', 'tap_stop'):
            self.assertEqual(render_event(make_event(action, 'started', {}), 'es'), [])

    def test_failed_completion_prepends_the_failure_line(self):
        event = completed('public_ip', {'exit_code': 1}, SimpleNamespace(ip='192.0.2.1'))
        lines = render_event(event, 'es')
        self.assertEqual(len(lines), 2)
        self.assertIn('192.0.2.1', lines[1])

    def test_unknown_action_gets_the_generic_sentence(self):
        self.assertEqual(len(render_event(completed('copy', {}, None), 'es')), 1)

    def test_capture_only_reports_an_end_when_it_finished_cleanly(self):
        self.assertEqual(len(render_event(completed('capture', {'interface': 'eth0', 'exit_code': 0}, None), 'es')), 1)
        self.assertEqual(render_event(completed('capture', {'interface': 'eth0'}, None), 'es'), [])


if __name__ == '__main__':
    unittest.main()
