"""Natural-language reports from use-case facts; no dependency on Qt."""
from pathlib import PurePath

from mulita.presentation.i18n import Translator
from mulita.presentation.texts import temperature_value, humidity_value, mbps
from mulita.presentation.tls import severity_label
from mulita.core.servers import kind_by_id


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
}
_EXPORTS = ('export', 'ping_export', 'export_many')


def render_event(event, language):
    tr = Translator(language).tr
    action, phase, p, value = event.action, event.phase, event.parameters, event.result
    detail = str(next((p[key] for key in ('target', 'interface', 'ssid', 'mac', 'name') if key in p), ''))
    if action == 'tap':
        config = p['config']
        detail = f'{config.entrante} → {config.saliente}'
    elif 'items' in p:
        detail = ', '.join(name for _, name in p['items'])
    label = tr(kind_by_id(p['kind']).title) if action == 'server' else tr(_LABELS.get(action, 'export'))
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
    if p.get('exit_code', 0) != 0 and not p.get('stopped'):
        lines.append(tr('journalFailed', subject=subject))
    if action in _EXPORTS:
        names = [PurePath(value).name] if action != 'export_many' else [name for _, name in p['items']]
        if action == 'ping_export':
            names.append(names[0][:-4] + '.statics.csv')
        return [tr('journalExport', name=name) for name in names]
    if action == 'ping':
        summary = value['summary']
        if summary.ready:
            sent = tr('journalSentOne') if summary.transmitted == '1' else tr('journalSent', count=summary.transmitted)
            received = tr('journalReceivedOne') if summary.received == '1' else tr('journalReceived', count=summary.received)
            result = tr('journalPingStats', sent=sent, received=received, loss=summary.loss)
            if summary.average:
                result += tr('journalPingAverage', average=summary.average)
        else:
            result = tr('journalPingIncomplete', count=value['replies'])
        lines.append(tr('journalPingResult', target=summary.target or detail, result=result))
    elif action == 'trace':
        route = '; '.join(tr('journalHop', hop=h.hop, address=h.address, loss=h.loss, average=h.average) for h in value)
        lines.append(tr('journalTraceResult', target=detail) + (route or tr('journalNoHops')))
    elif action == 'ports':
        rows = '; '.join(f'{item.host} {item.port}/{item.protocol} {item.state} {item.service}'.strip() for item in value)
        lines.append(tr('journalPorts') + (rows or tr('journalNoPorts')))
    elif action == 'discovery':
        hosts = '; '.join(f'{item.ip} ({item.mac})' for item in value)
        lines.append(tr('journalDiscovery', interface=detail) + (hosts or tr('journalNoHosts')))
    elif action == 'wol':
        lines.append(tr('journalWol', mac=value.mac, target=value.target, port=value.port))
    elif action == 'climate':
        lines.append(tr('journalClimate', temperature=temperature_value(value), humidity=humidity_value(value))
                     if value else tr('journalNoClimate'))
    elif action == 'speed':
        lines.append(tr('journalSpeed', download=mbps(value.download_bps), upload=mbps(value.upload_bps)))
    elif action == 'public_ip':
        lines.append(tr('journalPublicIp', ip=value.ip))
    elif action == 'vendor':
        lines.append(tr('journalVendor', mac=detail, name=value or tr('journalNoMatch')))
    elif action == 'capture':
        if p.get('exit_code') == 0 or p.get('stopped'):
            lines.append(tr('journalCaptureSaved', interface=detail, name=value.filename))
    elif action == 'tap':
        if value:
            lines.append(tr('journalTap', name=value))
    elif action == 'tls':
        counts = {}
        for finding in value:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        result = ', '.join(f'{severity_label(level, Translator(language))}: {count}' for level, count in counts.items())
        lines.append(tr('journalTls', target=detail, result=result or tr('journalNoFindings')))
    elif action == 'nmap':
        if value:
            hosts = ', '.join(h['ip'] for h in value.hosts if h.get('ip'))
            lines.append(tr('journalNmap', target=detail, status=tr('nmapStatus' + value.status.capitalize()),
                            hosts=hosts or tr('journalNone'), ports=value.open_ports or tr('journalNoneReported')))
    elif action == 'switch':
        neighbors = '; '.join(tr('journalNeighbor',
            name=row.get('name') or row.get('chassis') or tr('journalUnnamed'),
            port=row.get('port') or tr('journalUnknown')) for row in value.get('neighbors', []))
        lines.append(tr('journalSwitch', interface=value.get('interface', ''),
            status=tr('switchCancelled' if value['cancelled'] else 'switchComplete'),
            frames=value.get('frames', 0), neighbors=neighbors or tr('journalNoneObserved')))
    elif action in ('wifi_connect', 'wifi_reconnect'):
        if action == 'wifi_connect' or value:
            lines.append(tr('journalConnected', detail=detail))
    elif action == 'wifi_disconnect':
        lines.append(tr('journalDisconnected'))
    elif action in ('ipv4_ethernet', 'ipv4_wifi'):
        assigned = f'{value.address}/{value.prefix}' if value.address else tr('journalNoAddress')
        lines.append(tr('journalIpv4', interface=p.get('interface', 'Wi-Fi'), mode=value.mode.value, assigned=assigned))
    elif action == 'vlan':
        lines.append(tr('journalVlan', vlan=p['vlan'], interface=p['interface']) if p['enabled'] else
                     tr('journalNoVlan', interface=p['interface']))
    else:
        lines.append(tr('journalEnded', subject=subject))
    return lines
