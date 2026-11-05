"""Natural-language reports from use-case facts; no dependency on Qt."""
from dataclasses import replace

from mulita.presentation.i18n import Translator
from mulita.presentation.texts import temperature_value, humidity_value, mbps
from mulita.presentation.tls import severity_label
from mulita.presentation.facts import wifi_facts
from mulita.core.servers import kind_by_id
from mulita.core.journals import JournalRecord, technical_line
from mulita.core.journal_tests import category, TESTS
from mulita.core.events import OperationEvent
from mulita.core.event_payloads import (PingReport, TraceReport, PortsReport, DiscoveryReport,
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


def render_record(event: OperationEvent, language: str) -> JournalRecord | list[str]:
    lines = render_event(event, language)
    if not lines:
        return []
    tr = Translator(language).tr
    label = (tr(kind_by_id(event.parameters.kind).title) if event.action == 'server'
             else tr(_LABELS.get(event.action, 'export')))
    if event.action in _EXPORTS and category(event):
        label = tr(dict(TESTS)[category(event)])
    started = event.phase == 'started'
    # Reuse the redacted, localized report; never serialize raw operation parameters.
    description = '\n'.join(lines) if started else '\n'.join(render_event(replace(event, phase='started'), language)) or label
    results = '' if started else '\n'.join(lines)
    if event.action in _EXPORTS and event.phase == 'completed':
        assert isinstance(event.result, ExportReport)
        description = '\n'.join(lines)
        names = event.result.names
        results = '\n'.join(names)
    phase = 'failed' if event.parameters.exit_code and not event.parameters.stopped else event.phase
    return JournalRecord(event.operation_id, event.occurred_at.isoformat(timespec='seconds'),
                         label, phase, description, results,
                         tuple(technical_line(event.occurred_at, line) for line in lines))


def render_event(event: OperationEvent, language: str) -> list[str]:
    tr = Translator(language).tr
    action, phase, p, value = event.action, event.phase, event.parameters, event.result
    detail = p.detail
    label = tr(kind_by_id(p.kind).title) if action == 'server' else tr(_LABELS.get(action, 'export'))
    subject = f'{label} ({detail})' if detail else label
    if phase == 'failed':
        return [tr('journalFailed', subject=subject)]
    if phase == 'stop':
        return [tr('journalStop', subject=subject)]
    if phase == 'started':
        if action in _EXPORTS or action in ('climate', 'tap_stop'):
            return []
        key = {'ping': 'journalPing', 'trace': 'journalTrace', 'capture': 'journalCapture'}.get(action)
        return [tr(key, detail=detail) if key else tr('journalStarted', subject=subject)]
    if phase != 'completed':
        return []

    lines = []
    if p.exit_code not in (None, 0) and not p.stopped:
        lines.append(tr('journalFailed', subject=subject))
    if action in _EXPORTS:
        assert isinstance(value, ExportReport)
        names = value.names
        key = 'journalWebExport' if action == 'web_export' else 'journalExport'
        return [tr(key, name=name) for name in names]
    if isinstance(value, PingReport):
        summary = value.summary
        if summary.ready:
            sent = tr('journalSentOne') if summary.transmitted == '1' else tr('journalSent', count=summary.transmitted)
            received = tr('journalReceivedOne') if summary.received == '1' else tr('journalReceived', count=summary.received)
            result = tr('journalPingStats', sent=sent, received=received, loss=summary.loss)
            if summary.average:
                result += tr('journalPingAverage', average=summary.average)
        else:
            result = tr('journalPingIncomplete', count=value.replies)
        lines.append(tr('journalPingResult', target=summary.target or detail, result=result))
    elif isinstance(value, TraceReport):
        route = '; '.join(tr('journalHop', hop=h.hop, address=h.address, loss=h.loss, average=h.average) for h in value.hops)
        lines.append(tr('journalTraceResult', target=detail) + (route or tr('journalNoHops')))
    elif isinstance(value, PortsReport):
        rows = '; '.join(f'{item.host} {item.port}/{item.protocol} {item.state} {item.service}'.strip() for item in value.findings)
        lines.append(tr('journalPorts') + (rows or tr('journalNoPorts')))
    elif isinstance(value, DiscoveryReport):
        hosts = '; '.join(f'{item.ip} ({item.mac})' for item in value.hosts)
        lines.append(tr('journalDiscovery', interface=detail) + (hosts or tr('journalNoHosts')))
    elif isinstance(value, WakeReport):
        lines.append(tr('journalWol', mac=value.mac, target=value.target, port=value.port))
    elif isinstance(value, ClimateReport):
        lines.append(tr('journalClimate', temperature=temperature_value(value.reading), humidity=humidity_value(value.reading))
                     if value.reading else tr('journalNoClimate'))
    elif isinstance(value, SpeedTestResult):
        lines.append(tr('journalSpeed', download=mbps(value.download_bps), upload=mbps(value.upload_bps)))
    elif isinstance(value, PublicIpReport):
        lines.append(tr('journalPublicIp', ip=value.ip))
    elif isinstance(value, VendorReport):
        lines.append(tr('journalVendor', mac=detail, name=value.name or tr('journalNoMatch')))
    elif action == 'capture':
        if p.exit_code == 0 or p.stopped:
            lines.append(tr('journalCaptureEnded', interface=detail))
    elif isinstance(value, WifiLink):
        facts = '; '.join(f'{label}: {fact}' for label, fact in wifi_facts(value, Translator(language)))
        lines.append(tr('journalWifiInfo', result=facts or tr('journalNoneReported')))
    elif isinstance(value, TapReport):
        if value.filename:
            lines.append(tr('journalTap', name=value.filename))
    elif isinstance(value, TlsReport):
        result = ', '.join(f'{severity_label(item.severity, Translator(language))}: {item.count}' for item in value.counts)
        lines.append(tr('journalTls', target=detail, result=result or tr('journalNoFindings')))
    elif isinstance(value, NmapReport):
        if value.status:
            hosts = ', '.join(value.hosts)
            lines.append(tr('journalNmap', target=detail, status=tr('nmapStatus' + value.status.capitalize()),
                            hosts=hosts or tr('journalNone'), ports=value.open_ports or tr('journalNoneReported')))
    elif isinstance(value, SwitchReport):
        neighbors = '; '.join(tr('journalNeighbor',
            name=row.name or tr('journalUnnamed'),
            port=row.port or tr('journalUnknown')) for row in value.neighbors)
        lines.append(tr('journalSwitch', interface=value.interface,
            status=tr('switchCancelled' if value.cancelled else 'switchComplete'),
            frames=value.frames, neighbors=neighbors or tr('journalNoneObserved')))
    else:
        lines.append(tr('journalEnded', subject=subject))
    return lines
