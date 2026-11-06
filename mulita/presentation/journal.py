"""Natural-language reports from use-case facts; no dependency on Qt."""
from dataclasses import dataclass, replace

from mulita.presentation.i18n import Translator
from mulita.presentation.texts import temperature_value, humidity_value, mbps
from mulita.presentation.tls import severity_label
from mulita.presentation.facts import wifi_facts
from mulita.presentation.journal_results import formatted_results
from mulita.core.servers import kind_by_id
from mulita.core.journals import JournalRecord, technical_line
from mulita.core.journal_tests import category, TESTS
from mulita.core.events import OperationEvent
from mulita.core.event_payloads import (OperationParameters, PingReport, TraceReport, PortsReport, DiscoveryReport,
    WakeReport, ClimateReport, PublicIpReport, VendorReport, TapReport, TlsReport,
    NmapReport, SwitchReport, ExportReport)
from mulita.core.models import SpeedTestResult, WifiLink


_LABELS = {
    'ping': 'pingTitle', 'trace': 'tracesTitle', 'ports': 'scanPorts',
    'discovery': 'discoverTitle', 'capture': 'captureTitle', 'tap': 'homeTap',
    'tap_stop': 'homeTap', 'wol': 'toolWol', 'climate': 'toolClimate',
    'speed': 'toolSpeed', 'public_ip': 'publicIp', 'vendor': 'vendor',
    'tls': 'cyberTls', 'nmap': 'cyberNmap', 'switch': 'switchTitle',
    'wifi_connect': 'connect', 'wifi_reconnect': 'connect',
    'wifi_disconnect': 'wifiDisconnect', 'wifi_forget': 'wifiForget',
    'ipv4_wifi': 'wifiIp', 'ipv4_ethernet': 'ethInternal', 'vlan': 'ethInternal',
    'update': 'updateWord', 'restart': 'restartApp', 'poweroff': 'powerOff',
    'rename': 'rename', 'copy': 'copy', 'delete': 'delete',
    'wifi_info': 'wifiInfo',
}
_EXPORTS = ('export', 'ping_export', 'export_many', 'web_export')


def _label(event: OperationEvent, tr) -> str:
    if event.action == 'server':
        return tr(kind_by_id(event.parameters.kind).title)
    return tr(_LABELS.get(event.action, 'export'))


def render_record(event: OperationEvent, language: str) -> JournalRecord | list[str]:
    lines = render_event(event, language)
    if not lines:
        return []
    tr = Translator(language).tr
    label = _label(event, tr)
    if event.action in _EXPORTS and category(event):
        label = tr(dict(TESTS)[category(event)])
    started = event.phase == 'started'
    # Reuse the redacted, localized report; never serialize raw operation parameters.
    description = '\n'.join(lines) if started else '\n'.join(render_event(replace(event, phase='started'), language)) or label
    results = '' if started else formatted_results(event, language, '\n'.join(lines))
    if event.action in _EXPORTS and event.phase == 'completed':
        assert isinstance(event.result, ExportReport)
        description = '\n'.join(lines)
        names = event.result.names
        results = '\n'.join(names)
    phase = 'failed' if event.parameters.exit_code and not event.parameters.stopped else event.phase
    return JournalRecord(event.operation_id, event.occurred_at.isoformat(timespec='seconds'),
                         label, phase, description, results,
                         tuple(technical_line(event.occurred_at, line) for line in lines))


@dataclass(frozen=True)
class _Context:
    """Idioma, parametros y titulo del evento que se esta describiendo."""
    translator: Translator
    parameters: OperationParameters
    subject: str

    def tr(self, key: str, /, **parameters) -> str:
        return self.translator.tr(key, **parameters)

    @property
    def detail(self) -> str:
        return self.parameters.detail


def _ping(value: PingReport, c: _Context) -> list[str]:
    summary = value.summary
    if summary.ready:
        sent = c.tr('journalSentOne') if summary.transmitted == '1' else c.tr('journalSent', count=summary.transmitted)
        received = c.tr('journalReceivedOne') if summary.received == '1' else c.tr('journalReceived', count=summary.received)
        result = c.tr('journalPingStats', sent=sent, received=received, loss=summary.loss)
        if summary.average:
            result += c.tr('journalPingAverage', average=summary.average)
    else:
        result = c.tr('journalPingIncomplete', count=value.replies)
    return [c.tr('journalPingResult', target=summary.target or c.detail, result=result)]


def _trace(value: TraceReport, c: _Context) -> list[str]:
    route = '; '.join(c.tr('journalHop', hop=h.hop, address=h.address, loss=h.loss, average=h.average) for h in value.hops)
    return [c.tr('journalTraceResult', target=c.detail) + (route or c.tr('journalNoHops'))]


def _ports(value: PortsReport, c: _Context) -> list[str]:
    rows = '; '.join(f'{item.host} {item.port}/{item.protocol} {item.state} {item.service}'.strip() for item in value.findings)
    return [c.tr('journalPorts') + (rows or c.tr('journalNoPorts'))]


def _discovery(value: DiscoveryReport, c: _Context) -> list[str]:
    hosts = '; '.join(f'{item.ip} ({item.mac})' for item in value.hosts)
    return [c.tr('journalDiscovery', interface=c.detail) + (hosts or c.tr('journalNoHosts'))]


def _wake(value: WakeReport, c: _Context) -> list[str]:
    return [c.tr('journalWol', mac=value.mac, target=value.target, port=value.port)]


def _climate(value: ClimateReport, c: _Context) -> list[str]:
    if not value.reading:
        return [c.tr('journalNoClimate')]
    return [c.tr('journalClimate', temperature=temperature_value(value.reading), humidity=humidity_value(value.reading))]


def _speed(value: SpeedTestResult, c: _Context) -> list[str]:
    return [c.tr('journalSpeed', download=mbps(value.download_bps), upload=mbps(value.upload_bps))]


def _public_ip(value: PublicIpReport, c: _Context) -> list[str]:
    return [c.tr('journalPublicIp', ip=value.ip)]


def _vendor(value: VendorReport, c: _Context) -> list[str]:
    return [c.tr('journalVendor', mac=c.detail, name=value.name or c.tr('journalNoMatch'))]


def _wifi(value: WifiLink, c: _Context) -> list[str]:
    facts = '; '.join(f'{label}: {fact}' for label, fact in wifi_facts(value, c.translator))
    return [c.tr('journalWifiInfo', result=facts or c.tr('journalNoneReported'))]


def _tap(value: TapReport, c: _Context) -> list[str]:
    return [c.tr('journalTap', name=value.filename)] if value.filename else []


def _tls(value: TlsReport, c: _Context) -> list[str]:
    result = ', '.join(f'{severity_label(item.severity, c.translator)}: {item.count}' for item in value.counts)
    return [c.tr('journalTls', target=c.detail, result=result or c.tr('journalNoFindings'))]


def _nmap(value: NmapReport, c: _Context) -> list[str]:
    if not value.status:
        return []
    hosts = ', '.join(value.hosts)
    return [c.tr('journalNmap', target=c.detail, status=c.tr('nmapStatus' + value.status.capitalize()),
                 hosts=hosts or c.tr('journalNone'), ports=value.open_ports or c.tr('journalNoneReported'))]


def _switch(value: SwitchReport, c: _Context) -> list[str]:
    neighbors = '; '.join(c.tr('journalNeighbor', name=row.name or c.tr('journalUnnamed'),
                               port=row.port or c.tr('journalUnknown')) for row in value.neighbors)
    return [c.tr('journalSwitch', interface=value.interface,
                 status=c.tr('switchCancelled' if value.cancelled else 'switchComplete'),
                 frames=value.frames, neighbors=neighbors or c.tr('journalNoneObserved'))]


# Un tipo de resultado, una frase. Un constructor puede devolver [] si no hay nada que contar.
_SENTENCES = (
    (PingReport, _ping), (TraceReport, _trace), (PortsReport, _ports), (DiscoveryReport, _discovery),
    (WakeReport, _wake), (ClimateReport, _climate), (SpeedTestResult, _speed), (PublicIpReport, _public_ip),
    (VendorReport, _vendor), (WifiLink, _wifi), (TapReport, _tap), (TlsReport, _tls),
    (NmapReport, _nmap), (SwitchReport, _switch),
)
_QUIET_WHEN_STARTED = _EXPORTS + ('climate', 'tap_stop')
_START_KEYS = {'ping': 'journalPing', 'trace': 'journalTrace', 'capture': 'journalCapture'}


def _started(action: str, c: _Context) -> list[str]:
    if action in _QUIET_WHEN_STARTED:
        return []
    key = _START_KEYS.get(action)
    return [c.tr(key, detail=c.detail) if key else c.tr('journalStarted', subject=c.subject)]


def _completed(event: OperationEvent, c: _Context) -> list[str]:
    action, p, value = event.action, event.parameters, event.result
    failed = p.exit_code not in (None, 0) and not p.stopped
    if action in _EXPORTS:
        assert isinstance(value, ExportReport)
        key = 'journalWebExport' if action == 'web_export' else 'journalExport'
        return [c.tr(key, name=name) for name in value.names]
    lines = [c.tr('journalFailed', subject=c.subject)] if failed else []
    sentence = next((build for kind, build in _SENTENCES if isinstance(value, kind)), None)
    if sentence:
        return lines + sentence(value, c)
    if action == 'capture':
        if p.exit_code == 0 or p.stopped:
            lines.append(c.tr('journalCaptureEnded', interface=c.detail))
        return lines
    return lines + [c.tr('journalEnded', subject=c.subject)]


def render_event(event: OperationEvent, language: str) -> list[str]:
    translator = Translator(language)
    label = _label(event, translator.tr)
    detail = event.parameters.detail
    context = _Context(translator, event.parameters, f'{label} ({detail})' if detail else label)
    if event.phase == 'failed':
        return [context.tr('journalFailed', subject=context.subject)]
    if event.phase == 'stop':
        return [context.tr('journalStop', subject=context.subject)]
    if event.phase == 'started':
        return _started(event.action, context)
    if event.phase == 'completed':
        return _completed(event, context)
    return []
