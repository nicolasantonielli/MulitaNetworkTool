"""Readable diagnostic fields, shared by the device, web and CSV records."""
import re

from mulita.core.events import OperationEvent
from mulita.core.event_payloads import (PingReport, TraceReport, PortsReport, DiscoveryReport,
    WakeReport, ClimateReport, PublicIpReport, VendorReport, TapReport, TlsReport,
    NmapReport, SwitchReport, ExportReport)
from mulita.core.models import SpeedTestResult, WifiLink
from mulita.presentation.i18n import Translator
from mulita.presentation.facts import wifi_facts
from mulita.presentation.texts import temperature_value, humidity_value, mbps
from mulita.presentation.tls import severity_label


def formatted_results(event: OperationEvent, language: str, fallback: str) -> str:
    if event.phase != 'completed':
        return fallback
    tr = Translator(language).tr
    value = event.result
    def field(label, content):
        return f'{tr(label)}: {content}'
    rows = []
    if isinstance(value, PingReport):
        summary = value.summary
        rows.append(field('journalTarget', summary.target or event.parameters.detail))
        if summary.ready:
            rows += [field('pingSentLabel', summary.transmitted), field('pingReceivedLabel', summary.received),
                     field('pingLossLabel', summary.loss)]
            if summary.average:
                rows.append(field('pingAvgLabel', summary.average + ' ms'))
        else:
            rows.append(tr('journalPingIncomplete', count=value.replies))
    elif isinstance(value, TraceReport):
        rows = [tr('journalHop', hop=h.hop, address=h.address, loss=h.loss, average=h.average) for h in value.hops]
    elif isinstance(value, PortsReport):
        rows = [f'{item.host} · {item.port}/{item.protocol} · {item.state}'
                + (f' · {item.service}' if item.service else '') for item in value.findings]
    elif isinstance(value, DiscoveryReport):
        rows = [f'{host.ip} · MAC: {host.mac}' for host in value.hosts]
    elif isinstance(value, WakeReport):
        rows = [field('factMac', value.mac), field('journalTarget', value.target), field('journalPort', value.port)]
    elif isinstance(value, ClimateReport) and value.reading:
        rows = [field('temperature', temperature_value(value.reading)), field('humidity', humidity_value(value.reading))]
    elif isinstance(value, SpeedTestResult):
        rows = [field('download', mbps(value.download_bps) + ' Mbps'), field('upload', mbps(value.upload_bps) + ' Mbps')]
    elif isinstance(value, PublicIpReport):
        rows = [field('publicIp', value.ip)]
    elif isinstance(value, VendorReport):
        rows = [field('factMac', event.parameters.detail), field('vendor', value.name or tr('journalNoMatch'))]
    elif isinstance(value, WifiLink):
        rows = [f'{label}: {fact}' for label, fact in wifi_facts(value, Translator(language))]
    elif isinstance(value, TapReport) and value.filename:
        rows = [field('fileName', value.filename)]
    elif isinstance(value, TlsReport):
        rows = [f'{severity_label(item.severity, Translator(language))}: {item.count}' for item in value.counts]
    elif isinstance(value, NmapReport) and value.status:
        rows = [field('status', tr('nmapStatus' + value.status.capitalize())),
                field('journalHosts', '\n' + '\n'.join('• ' + host for host in value.hosts) if value.hosts else tr('journalNone')),
                field('journalOpenPorts', value.open_ports or tr('journalNoneReported'))]
    elif isinstance(value, SwitchReport):
        rows = [field('factIface', value.interface), field('status', tr('switchCancelled' if value.cancelled else 'switchComplete')),
                field('journalFrames', value.frames), tr('journalNeighbors') + ':']
        rows += [tr('journalNeighbor', name=row.name or tr('journalUnnamed'), port=row.port or tr('journalUnknown'))
                 for row in value.neighbors] or [tr('journalNoneObserved')]
    elif isinstance(value, ExportReport):
        rows = list(value.names)
    if not rows:
        return fallback
    if event.parameters.exit_code not in (None, 0) and not event.parameters.stopped:
        rows.insert(0, tr('journalPartialResults'))
    return '\n'.join(rows)


def display_results(text: str) -> str:
    """Add visual breaks to old prose; never rewrite or migrate stored history."""
    if '\n' in text:
        return text
    text = text.replace('; ', ';\n')
    text = re.sub(r'\. (?=[A-ZÁÉÍÓÚÜÑ])', '.\n', text)
    # Only the headings emitted by previous journal formatters, not arbitrary addresses.
    text = re.sub(r'^(Resultado del ping a [^\n]+?|Ping results for [^\n]+?|Traza a [^\n]+?|Trace to [^\n]+?|'
                  r'Resultado del escaneo de puertos|Port scan results|Descubrimiento en [^\n]+?|Discovery on [^\n]+?|'
                  r'Se consultó la información Wi-Fi|Wi-Fi information was checked): ', r'\1:\n', text, count=1)
    return text
