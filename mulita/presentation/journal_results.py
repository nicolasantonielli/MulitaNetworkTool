"""Readable diagnostic fields, shared by the device, web and CSV records."""
import re

from mulita.core.events import OperationEvent
from mulita.core.event_payloads import (OperationParameters, PingReport, TraceReport, PortsReport,
    DiscoveryReport, WakeReport, ClimateReport, PublicIpReport, VendorReport, TapReport, TlsReport,
    NmapReport, SwitchReport, ExportReport)
from mulita.core.models import SpeedTestResult, WifiLink
from mulita.presentation.i18n import Translator
from mulita.presentation.facts import wifi_facts
from mulita.presentation.texts import temperature_value, humidity_value, mbps
from mulita.presentation.tls import severity_label


class _Fields:
    """Traduce las etiquetas y arma las filas `etiqueta: valor` de un evento."""

    def __init__(self, language: str, parameters: OperationParameters):
        self.translator = Translator(language)
        self.parameters = parameters

    def tr(self, key: str, /, **parameters) -> str:
        return self.translator.tr(key, **parameters)

    def field(self, label: str, content) -> str:
        return f'{self.tr(label)}: {content}'


def _ping(value: PingReport, f: _Fields) -> list[str]:
    summary = value.summary
    rows = [f.field('journalTarget', summary.target or f.parameters.detail)]
    if not summary.ready:
        return rows + [f.tr('journalPingIncomplete', count=value.replies)]
    rows += [f.field('pingSentLabel', summary.transmitted), f.field('pingReceivedLabel', summary.received),
             f.field('pingLossLabel', summary.loss)]
    if summary.average:
        rows.append(f.field('pingAvgLabel', summary.average + ' ms'))
    return rows


def _trace(value: TraceReport, f: _Fields) -> list[str]:
    return [f.tr('journalHop', hop=h.hop, address=h.address, loss=h.loss, average=h.average) for h in value.hops]


def _ports(value: PortsReport, f: _Fields) -> list[str]:
    return [f'{item.host} · {item.port}/{item.protocol} · {item.state}'
            + (f' · {item.service}' if item.service else '') for item in value.findings]


def _discovery(value: DiscoveryReport, f: _Fields) -> list[str]:
    return [f'{host.ip} · MAC: {host.mac}' for host in value.hosts]


def _wake(value: WakeReport, f: _Fields) -> list[str]:
    return [f.field('factMac', value.mac), f.field('journalTarget', value.target),
            f.field('journalPort', value.port)]


def _climate(value: ClimateReport, f: _Fields) -> list[str]:
    if not value.reading:
        return []
    return [f.field('temperature', temperature_value(value.reading)),
            f.field('humidity', humidity_value(value.reading))]


def _speed(value: SpeedTestResult, f: _Fields) -> list[str]:
    return [f.field('download', mbps(value.download_bps) + ' Mbps'),
            f.field('upload', mbps(value.upload_bps) + ' Mbps')]


def _public_ip(value: PublicIpReport, f: _Fields) -> list[str]:
    return [f.field('publicIp', value.ip)]


def _vendor(value: VendorReport, f: _Fields) -> list[str]:
    return [f.field('factMac', f.parameters.detail), f.field('vendor', value.name or f.tr('journalNoMatch'))]


def _wifi(value: WifiLink, f: _Fields) -> list[str]:
    return [f'{label}: {fact}' for label, fact in wifi_facts(value, f.translator)]


def _tap(value: TapReport, f: _Fields) -> list[str]:
    return [f.field('fileName', value.filename)] if value.filename else []


def _tls(value: TlsReport, f: _Fields) -> list[str]:
    return [f'{severity_label(item.severity, f.translator)}: {item.count}' for item in value.counts]


def _nmap(value: NmapReport, f: _Fields) -> list[str]:
    if not value.status:
        return []
    hosts = '\n' + '\n'.join('• ' + host for host in value.hosts) if value.hosts else f.tr('journalNone')
    return [f.field('status', f.tr('nmapStatus' + value.status.capitalize())),
            f.field('journalHosts', hosts),
            f.field('journalOpenPorts', value.open_ports or f.tr('journalNoneReported'))]


def _switch(value: SwitchReport, f: _Fields) -> list[str]:
    rows = [f.field('factIface', value.interface),
            f.field('status', f.tr('switchCancelled' if value.cancelled else 'switchComplete')),
            f.field('journalFrames', value.frames), f.tr('journalNeighbors') + ':']
    neighbors = [f.tr('journalNeighbor', name=row.name or f.tr('journalUnnamed'), port=row.port or f.tr('journalUnknown'))
                 for row in value.neighbors]
    return rows + (neighbors or [f.tr('journalNoneObserved')])


def _export(value: ExportReport, f: _Fields) -> list[str]:
    return list(value.names)


# Un tipo de resultado, un constructor de filas. Un constructor que devuelve [] deja el texto de respaldo.
_ROWS = (
    (PingReport, _ping), (TraceReport, _trace), (PortsReport, _ports), (DiscoveryReport, _discovery),
    (WakeReport, _wake), (ClimateReport, _climate), (SpeedTestResult, _speed), (PublicIpReport, _public_ip),
    (VendorReport, _vendor), (WifiLink, _wifi), (TapReport, _tap), (TlsReport, _tls),
    (NmapReport, _nmap), (SwitchReport, _switch), (ExportReport, _export),
)


def formatted_results(event: OperationEvent, language: str, fallback: str) -> str:
    if event.phase != 'completed':
        return fallback
    fields = _Fields(language, event.parameters)
    build = next((builder for kind, builder in _ROWS if isinstance(event.result, kind)), None)
    rows = build(event.result, fields) if build else []
    if not rows:
        return fallback
    parameters = event.parameters
    if parameters.exit_code not in (None, 0) and not parameters.stopped:
        rows.insert(0, fields.tr('journalPartialResults'))
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
