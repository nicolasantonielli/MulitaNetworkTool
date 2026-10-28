"""Perfiles de Nmap, armado del comando, lectura del XML y comparación.

El comando se arma como lista de argumentos. No pasa por un shell: un destino
con caracteres raros se rechaza, no ejecuta otro programa.
"""
from __future__ import annotations

import ipaddress
import re
import shlex
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable
from xml.etree import ElementTree

from mulita.core import validation
from mulita.core.errors import ValidationError
from mulita.presentation.i18n import tr

TLS_PORTS = '443,465,636,853,993,995,8443'
HTTP_PORTS = '80,443,8080,8443'
_TIMING = {'T2', 'T3', 'T4'}
_HOST = re.compile(
    r'^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)'
    r'(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$')
_RANGE = re.compile(r'^(\d{1,3}(?:\.\d{1,3}){3})-(\d{1,3})$')
_PORT = re.compile(r'^\d{1,5}(?:-\d{1,5})?(?:,\d{1,5}(?:-\d{1,5})?)*$')
_SCRIPT = re.compile(r'^[A-Za-z0-9_.-]+$')
_TIMING_FLAG = re.compile(r'^-T[0-5]$')
_ELAPSED = re.compile(r'Stats:\s*(\d+:\d\d:\d\d)\s+elapsed')
_UNDERGOING = re.compile(r'undergoing\s+(.+)$')
_PHASE = re.compile(r'^(.*?)\s+Timing:\s+About\s+([\d.]+)%\s+done(?:;.*?\(([0-9:]+) remaining\))?')
_VULNERABLE = re.compile(r'(?<!NOT )VULNERABLE', re.IGNORECASE)
_FORBIDDEN = {'-oN', '-oX', '-oG', '-oA', '-oS', '--append-output'}
_TAKES_VALUE = {
    '-p', '--top-ports', '-e', '--exclude', '--script', '--script-args', '-iL', '--excludefile',
    '--stats-every', '--version-intensity', '-S', '-g', '--source-port', '-D', '--data',
    '--data-string', '--data-length', '--stylesheet', '--datadir', '--servicedb', '--versiondb',
    '--script-timeout', '--dns-servers', '--proxies', '-oN', '-oX', '-oG', '-oA', '-oS',
    '--max-retries', '--host-timeout', '--min-rate', '--max-rate', '--min-parallelism',
    '--max-parallelism', '--max-rtt-timeout', '--min-rtt-timeout', '--initial-rtt-timeout',
}
_FILE_OPTIONS = {'-iL', '--excludefile'}
_PRIVILEGE = ('requires root', 'raw socket', 'raw sockets', 'privileges')

Resolver = Callable[[str], str | None]


@dataclass(frozen=True)
class Profile:
    id: str
    title: str
    subtitle: str
    hint: str
    icon: str
    flags: tuple[str, ...]
    ports: str = 'none'          # none | list | previous | udp
    port_default: str = ''
    recommended: bool = False
    needs_interface: bool = False
    timing: bool = False         # el comando ya lleva -T3 y se puede cambiar
    locked_no_dns: bool = False  # -n ya está en el comando
    sni: bool = False
    raw: bool = False
    scripts: tuple[str, ...] = ()
    catalog: bool = False
    slow: bool = False
    fallback: str = ''
    custom: bool = False

    def view(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'subtitle': self.subtitle,
            'hint': self.hint,
            'icon': self.icon,
            'builtin': True,
            'custom': self.custom,
            'recommended': self.recommended,
            'ports': self.ports,
            'portDefault': self.port_default,
            'needsInterface': self.needs_interface,
            'timing': self.timing,
            'lockedNoDns': self.locked_no_dns,
            'sni': self.sni,
            'raw': self.raw,
            'catalog': self.catalog,
            'slow': self.slow,
            'fallback': self.fallback,
            'arguments': '',
            'description': '',
        }


@dataclass(frozen=True)
class Check:
    id: str
    title: str
    detail: str
    services: str
    impact: str

    def view(self) -> dict:
        return {'id': self.id, 'title': self.title, 'detail': self.detail,
                'services': self.services, 'impact': self.impact}


# El orden es el de la pantalla. `flags` es la parte fija; el destino va al final.
PROFILES: tuple[Profile, ...] = (
    Profile('discover', 'nmapProfDiscover', 'nmapProfDiscoverSub', 'nmapProfDiscoverHint', 'search',
            ('-sn', '-n'), locked_no_dns=True),
    Profile('arp', 'nmapProfArp', 'nmapProfArpSub', 'nmapProfArpHint', 'ethernet',
            ('-sn', '-PR', '-n'), needs_interface=True, locked_no_dns=True, raw=True),
    Profile('tcp-fast', 'nmapProfFast', 'nmapProfFastSub', 'nmapProfFastHint', 'scan',
            ('-sT', '-T3', '--top-ports', '100', '--reason'), timing=True, recommended=True),
    Profile('tcp-standard', 'nmapProfStandard', 'nmapProfStandardSub', 'nmapProfStandardHint', 'scan',
            ('-sT', '-T3', '--top-ports', '1000', '--reason'), timing=True),
    Profile('tcp-all', 'nmapProfAll', 'nmapProfAllSub', 'nmapProfAllHint', 'scan',
            ('-sT', '-T3', '-p-', '--reason'), timing=True, slow=True),
    Profile('syn', 'nmapProfSyn', 'nmapProfSynSub', 'nmapProfSynHint', 'scan',
            ('-sS', '-T3', '--top-ports', '1000', '--reason'), timing=True, raw=True, fallback='tcp-standard'),
    Profile('ports', 'nmapProfPorts', 'nmapProfPortsSub', 'nmapProfPortsHint', 'scan',
            ('-sT', '-T3', '--reason'), ports='list', port_default='22,80,443', timing=True),
    Profile('versions', 'nmapProfVersions', 'nmapProfVersionsSub', 'nmapProfVersionsHint', 'info',
            ('-sT', '-sV', '-T3', '--reason'), ports='previous', port_default='*', timing=True),
    Profile('os', 'nmapProfOs', 'nmapProfOsSub', 'nmapProfOsHint', 'info',
            ('-sS', '-O', '--osscan-limit', '-T3'), timing=True, raw=True),
    Profile('udp', 'nmapProfUdp', 'nmapProfUdpSub', 'nmapProfUdpHint', 'scan',
            ('-sU', '-sV', '-T3', '--reason'), ports='udp', timing=True, raw=True, slow=True),
    Profile('tls-cert', 'nmapProfCert', 'nmapProfCertSub', 'nmapProfCertHint', 'lock',
            ('-sT', '-sV'), ports='list', port_default=TLS_PORTS, sni=True, scripts=('ssl-cert',)),
    Profile('tls-ciphers', 'nmapProfCiphers', 'nmapProfCiphersSub', 'nmapProfCiphersHint', 'lock',
            ('-sT', '-sV'), ports='list', port_default=TLS_PORTS, sni=True,
            scripts=('ssl-cert', 'ssl-enum-ciphers')),
    Profile('smb', 'nmapProfSmb', 'nmapProfSmbSub', 'nmapProfSmbHint', 'shield',
            ('-sT', '-p', '139,445', '--script', 'smb-protocols,smb-security-mode,smb2-security-mode'),
            scripts=('smb-protocols', 'smb-security-mode', 'smb2-security-mode')),
    Profile('ssh', 'nmapProfSsh', 'nmapProfSshSub', 'nmapProfSshHint', 'lock',
            ('-sT', '-sV', '--script', 'ssh-hostkey,ssh2-enum-algos', '-v'),
            ports='list', port_default='22', scripts=('ssh-hostkey', 'ssh2-enum-algos')),
    Profile('http', 'nmapProfHttp', 'nmapProfHttpSub', 'nmapProfHttpHint', 'globe',
            ('-sT', '-sV', '--script', 'http-title,http-headers'),
            ports='list', port_default=HTTP_PORTS, scripts=('http-title', 'http-headers')),
    Profile('checks', 'nmapProfChecks', 'nmapProfChecksSub', 'nmapProfChecksHint', 'bug',
            ('-sT', '-sV', '-T3'), ports='previous', port_default='*', timing=True, catalog=True),
    Profile('custom', 'nmapProfCustom', 'nmapProfCustomSub', 'nmapProfCustomHint', 'wrench',
            (), custom=True),
)

CHECKS: tuple[Check, ...] = (
    Check('ssl-heartbleed', 'nmapCheckHeartbleed', 'nmapCheckHeartbleedDetail',
          'nmapCheckTlsServices', 'nmapCheckHeartbleedImpact'),
    Check('ssl-poodle', 'nmapCheckPoodle', 'nmapCheckPoodleDetail',
          'nmapCheckTlsServices', 'nmapCheckPoodleImpact'),
    Check('ssl-ccs-injection', 'nmapCheckCcs', 'nmapCheckCcsDetail',
          'nmapCheckTlsServices', 'nmapCheckCcsImpact'),
    Check('smb-vuln-ms17-010', 'nmapCheckMs17010', 'nmapCheckMs17010Detail',
          'nmapCheckSmbServices', 'nmapCheckMs17010Impact'),
    Check('smb-vuln-ms08-067', 'nmapCheckMs08067', 'nmapCheckMs08067Detail',
          'nmapCheckSmbServices', 'nmapCheckMs08067Impact'),
    Check('rdp-vuln-ms12-020', 'nmapCheckRdp', 'nmapCheckRdpDetail',
          'nmapCheckRdpServices', 'nmapCheckRdpImpact'),
    Check('ftp-anon', 'nmapCheckFtp', 'nmapCheckFtpDetail',
          'nmapCheckFtpServices', 'nmapCheckFtpImpact'),
)

_BY_ID = {item.id: item for item in PROFILES}
_CHECK_IDS = {item.id for item in CHECKS}


def profile_by_id(profile_id: str) -> Profile:
    try:
        return _BY_ID[profile_id]
    except KeyError:
        raise ValidationError(tr('nmapBadProfile', value=profile_id or tr('empty'))) from None


def profiles_view(user_profiles: list[dict]) -> list[dict]:
    items = [item.view() for item in PROFILES]
    for saved in user_profiles:
        items.append({
            'id': saved['id'],
            'title': saved['name'],
            'subtitle': 'nmapProfOwnSub',
            'hint': saved.get('description') or 'nmapProfCustomHint',
            'icon': 'wrench',
            'builtin': False,
            'custom': True,
            'recommended': False,
            'ports': 'none',
            'portDefault': '',
            'needsInterface': False,
            'timing': False,
            'lockedNoDns': False,
            'sni': False,
            'raw': False,
            'catalog': False,
            'slow': False,
            'fallback': '',
            'arguments': saved.get('arguments', ''),
            'description': saved.get('description', ''),
        })
    return items


def checks_view() -> list[dict]:
    return [item.view() for item in CHECKS]


@dataclass
class Compiled:
    profile_id: str
    command: str
    args: list[str]
    display: list[str]
    target_count: int
    notes: list[str] = field(default_factory=list)
    scripts: tuple[str, ...] = ()


def compile_scan(data: dict, user_profiles: dict[str, dict] | None = None,
                 resolve_file: Resolver | None = None) -> Compiled:
    """Arma el comando y explica de dónde sale el destino. No habla con Nmap."""
    user_profiles = user_profiles or {}
    resolve_file = resolve_file or (lambda _value: None)
    profile_id = str(data.get('profile') or '')
    saved = user_profiles.get(profile_id)
    profile = None if saved or profile_id == 'custom' else profile_by_id(profile_id)
    if saved is None and profile is None and profile_id != 'custom':
        profile_by_id(profile_id)
    timing = str(data.get('timing') or 'T3')
    if timing not in _TIMING:
        raise ValidationError(tr('nmapBadTiming', value=timing))
    notes: list[str] = []
    if profile is not None and not profile.custom:
        compiled = _compile_builtin(profile, data, timing, notes)
    else:
        if str(data.get('custom') or '').strip():
            line = str(data.get('custom') or '')
        else:
            line = str((saved or {}).get('arguments') or '')
        compiled = _compile_custom(line, str(data.get('targets') or ''), resolve_file, notes)
        compiled.profile_id = profile_id or 'custom'
    if data.get('noDiscovery') or data.get('no_discovery'):
        notes.append(tr('nmapPnWarn'))
    notes.append(tr('nmapReportsNote'))
    compiled.notes = notes
    compiled.command = 'nmap ' + ' '.join(shlex.quote(part) for part in compiled.display)
    return compiled


def _compile_builtin(profile: Profile, data: dict, timing: str, notes: list[str]) -> Compiled:
    targets = parse_targets(str(data.get('targets') or ''))
    args = _with_timing(list(profile.flags), timing, profile.timing)
    _insert_ports(args, profile, data)
    if profile.scripts:
        if '--script' not in args:
            args.extend(['--script', ','.join(profile.scripts)])
    elif profile.catalog:
        chosen = _catalog_scripts(data.get('scripts') or [])
        args.extend(['--script', ','.join(chosen)])
    else:
        chosen = ()
    if profile.sni and str(data.get('sni') or '').strip():
        args.extend(['--script-args', 'tls.servername=' + validation.dns_name(str(data['sni']))])
    _modifiers(args, profile, data)
    _runtime_flags(args)
    scripts = profile.scripts or (chosen if profile.catalog else ())
    display = args + targets
    return Compiled(profile.id, '', list(display), list(display), len(targets), scripts=tuple(scripts))


def _compile_custom(line: str, targets_field: str, resolve_file: Resolver, notes: list[str]) -> Compiled:
    parsed = parse_custom(line)
    display: list[str] = []
    resolved: list[str] = []
    inline_targets: list[str] = []
    index = 0
    while index < len(parsed):
        token = parsed[index]
        _reject_output_option(token)
        if token in _TAKES_VALUE or token.split('=', 1)[0] in _FILE_OPTIONS:
            if index + 1 >= len(parsed):
                raise ValidationError(tr('nmapOptionNeedsValue', option=token))
            value = parsed[index + 1]
            _reject_output_option(token)
            shown, real = _resolve_option(token, value, resolve_file)
            display.extend([token, shown])
            resolved.extend([token, real])
            index += 2
            continue
        if token.startswith('--script='):
            shown, real = _resolve_option('--script', token.split('=', 1)[1], resolve_file)
            display.append('--script=' + shown)
            resolved.append('--script=' + real)
            index += 1
            continue
        if token.startswith('-'):
            display.append(token)
            resolved.append(token)
            index += 1
            continue
        inline_targets.append(_one_target(token))
        index += 1
    listed = '-iL' in parsed
    if inline_targets:
        notes.append(tr('nmapTargetInLine'))
        targets = inline_targets
    elif listed:
        notes.append(tr('nmapTargetInFile'))
        targets = []
    else:
        targets = parse_targets(targets_field)
        notes.append(tr('nmapTargetInField'))
    _runtime_flags(resolved)
    _runtime_flags(display)
    return Compiled('custom', '', resolved + targets, display + targets, len(targets))


def saved_arguments(line: str) -> str:
    """Acepta la línea de un perfil propio y rechaza opciones que pisan los archivos de Mulita."""
    for token in parse_custom(line):
        _reject_output_option(token)
    return line.strip()


def parse_custom(line: str) -> list[str]:
    """Acepta argumentos o un comando pegado que empiece por `nmap`. Solo quita ese nombre."""
    text = (line or '').strip()
    lowered = text.lower()
    for prefix in ('nmap.exe', 'nmap'):
        if lowered.startswith(prefix) and (len(text) == len(prefix) or text[len(prefix)].isspace()):
            text = text[len(prefix):].strip()
            break
    if not text:
        raise ValidationError(tr('nmapNeedArgs'))
    try:
        args = shlex.split(text, posix=True)
    except ValueError as exc:
        raise ValidationError(tr('nmapBadArgs', value=exc)) from exc
    if not args:
        raise ValidationError(tr('nmapNeedArgs'))
    return args


def parse_targets(text: str) -> list[str]:
    tokens = (text or '').split()
    if not tokens:
        raise ValidationError(tr('nmapNeedTarget'))
    return [_one_target(token) for token in tokens]


def parse_ports(text: str) -> str:
    value = (text or '').replace(' ', '')
    if not value or not _PORT.fullmatch(value):
        raise ValidationError(tr('nmapBadPort', value=value or tr('empty')))
    for part in value.split(','):
        if '-' in part:
            start, end = (int(piece) for piece in part.split('-', 1))
            if not 1 <= start <= end <= 65535:
                raise ValidationError(tr('nmapBadPort', value=part))
        elif not 1 <= int(part) <= 65535:
            raise ValidationError(tr('nmapBadPort', value=part))
    return value


def privilege_error(text: str) -> bool:
    lowered = (text or '').lower()
    return any(mark in lowered for mark in _PRIVILEGE)


def _one_target(token: str) -> str:
    if token.startswith('-') or any(char in token for char in ';&|$`<>\'"\\'):
        raise ValidationError(tr('nmapBadTarget', value=token))
    if '/' in token:
        try:
            ipaddress.ip_network(token, strict=False)
        except ValueError:
            raise ValidationError(tr('nmapBadTarget', value=token)) from None
        return token
    if ':' in token:
        try:
            ipaddress.ip_address(token.split('%', 1)[0])
        except ValueError:
            raise ValidationError(tr('nmapBadTarget', value=token)) from None
        return token
    ranged = _RANGE.fullmatch(token)
    if ranged:
        try:
            ipaddress.ip_address(ranged.group(1))
        except ValueError:
            raise ValidationError(tr('nmapBadTarget', value=token)) from None
        start = int(ranged.group(1).rsplit('.', 1)[1])
        end = int(ranged.group(2))
        if not 0 <= end <= 255 or start > end:
            raise ValidationError(tr('nmapBadTarget', value=token))
        return token
    try:
        ipaddress.ip_address(token)
        return token
    except ValueError:
        pass
    if _HOST.fullmatch(token):
        return token
    raise ValidationError(tr('nmapBadTarget', value=token))


def _with_timing(flags: list[str], timing: str, always: bool) -> list[str]:
    token = '-' + timing
    found = False
    result = []
    for flag in flags:
        if _TIMING_FLAG.fullmatch(flag):
            result.append(token)
            found = True
        else:
            result.append(flag)
    if not found and (always or timing != 'T3'):
        result.append(token)
    return result


def _insert_ports(args: list[str], profile: Profile, data: dict) -> None:
    if profile.ports == 'none':
        return
    if profile.ports == 'udp':
        mode = str(data.get('udp') or 'top20')
        if mode == 'top100':
            extra = ['--top-ports', '100']
        elif mode == 'custom':
            extra = ['-p', parse_ports(str(data.get('ports') or ''))]
        elif mode == 'top20':
            extra = ['--top-ports', '20']
        else:
            raise ValidationError(tr('nmapBadUdp', value=mode))
    else:
        raw = str(data.get('ports') or profile.port_default)
        if profile.ports == 'previous' and raw.strip() in ('', '*'):
            extra = ['--top-ports', '1000']
        else:
            extra = ['-p', parse_ports(raw)]
    if '--reason' in args:
        at = args.index('--reason')
        args[at:at] = extra
    elif '--script' in args:
        at = args.index('--script')
        args[at:at] = extra
    else:
        args.extend(extra)


def _catalog_scripts(chosen) -> tuple[str, ...]:
    if not isinstance(chosen, list) or not chosen:
        raise ValidationError(tr('nmapNeedScript'))
    names = []
    for item in chosen:
        name = str(item)
        if name not in _CHECK_IDS:
            raise ValidationError(tr('nmapBadScript', value=name))
        if name not in names:
            names.append(name)
    return tuple(names)


def _modifiers(args: list[str], profile: Profile, data: dict) -> None:
    if data.get('noDns') and not profile.locked_no_dns and '-n' not in args and '-R' not in args:
        args.append('-n')
    if data.get('noDiscovery') and '-Pn' not in args:
        args.append('-Pn')
    interface = str(data.get('interface') or '').strip()
    if profile.needs_interface or interface:
        if not interface and profile.needs_interface:
            raise ValidationError(tr('nmapNeedIface'))
        if interface:
            args.extend(['-e', validation.interface_name(interface)])
    exclude = str(data.get('exclude') or '').replace(',', ' ')
    if exclude.strip():
        args.extend(['--exclude', ','.join(parse_targets(exclude))])


def _runtime_flags(args: list[str]) -> None:
    """`-v` y el avance cada 5 s. No se duplican si el perfil o la línea ya los traen."""
    front = []
    if '-v' not in args and '-vv' not in args and '--verbose' not in args:
        front.append('-v')
    if '--stats-every' not in args:
        front.extend(['--stats-every', '5s'])
    args[:0] = front


def _reject_output_option(token: str) -> None:
    if token in _FORBIDDEN or token.startswith(('-oN', '-oX', '-oG', '-oA', '-oS')):
        raise ValidationError(tr('nmapOutputManaged'))


def _resolve_option(option: str, value: str, resolve_file: Resolver) -> tuple[str, str]:
    if option in _FILE_OPTIONS or option == '-iL':
        return value, _existing_file(value, resolve_file)
    if option == '--script':
        shown, real = [], []
        for name in (part.strip() for part in value.split(',')):
            if not name:
                continue
            if name.startswith('@') or '/' in name or '\\' in name:
                shown.append(name)
                real.append(_existing_file(name, resolve_file))
            elif not _SCRIPT.fullmatch(name) or name == 'vuln':
                raise ValidationError(tr('nmapBadScript', value=name or tr('empty')))
            else:
                shown.append(name)
                real.append(name)
        if not shown:
            raise ValidationError(tr('nmapNeedScript'))
        return ','.join(shown), ','.join(real)
    return value, value


def _existing_file(value: str, resolve_file: Resolver) -> str:
    resolved = resolve_file(value)
    if not resolved:
        raise ValidationError(tr('nmapBadFile', name=value))
    return resolved


# --- Avance informado por Nmap -----------------------------------------------------------


@dataclass
class Progress:
    elapsed: str = ''
    phase: str = ''
    percent: str = ''
    remaining: str = ''
    phase_only: bool = False

    def view(self) -> dict:
        return {'elapsed': self.elapsed, 'phase': self.phase, 'percent': self.percent,
                'remaining': self.remaining, 'phaseOnly': self.phase_only}


def update_progress(progress: Progress, text: str) -> bool:
    """Solo copia lo que Nmap escribió. Si no hay porcentaje, queda vacío."""
    changed = False
    for line in (text or '').splitlines():
        line = line.strip()
        elapsed = _ELAPSED.search(line)
        if elapsed:
            progress.elapsed = elapsed.group(1)
            changed = True
            undergoing = _UNDERGOING.search(line)
            if undergoing:
                progress.phase = undergoing.group(1).strip()
        phase = _PHASE.search(line)
        if phase:
            progress.phase = phase.group(1).strip() or progress.phase
            progress.percent = phase.group(2)
            progress.remaining = phase.group(3) or ''
            progress.phase_only = True
            changed = True
    return changed


# --- XML ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanDocument:
    hosts: tuple[dict, ...]
    partial: bool
    complete: bool


def parse_xml(text: str, today: date | None = None) -> ScanDocument:
    """Lee el XML. Si está cortado, conserva los equipos que quedaron completos."""
    raw = (text or '').strip()
    if not raw:
        return ScanDocument((), True, False)
    try:
        root = ElementTree.fromstring(raw)
        repaired = False
    except ElementTree.ParseError:
        cut = raw.rfind('</host>')
        if cut < 0 or '<nmaprun' not in raw[:cut]:
            return ScanDocument((), True, False)
        try:
            root = ElementTree.fromstring(raw[:cut + len('</host>')] + '</nmaprun>')
        except ElementTree.ParseError:
            return ScanDocument((), True, False)
        repaired = True
    hosts = tuple(_host(node, today or date.today()) for node in root.findall('host'))
    finished = root.find('runstats/finished')
    complete = finished is not None and finished.get('exit') == 'success' and not repaired
    return ScanDocument(hosts, not complete, complete)


def _host(node, today: date) -> dict:
    status = node.find('status')
    ip = mac = vendor = ''
    for address in node.findall('address'):
        kind = address.get('addrtype')
        if kind == 'mac':
            mac = address.get('addr', '')
            vendor = address.get('vendor', '')
        elif kind in ('ipv4', 'ipv6') and not ip:
            ip = address.get('addr', '')
    names = [item.get('name', '') for item in node.findall('hostnames/hostname') if item.get('name')]
    matches = [{'name': item.get('name', ''), 'accuracy': item.get('accuracy', '')}
               for item in node.findall('os/osmatch') if item.get('name')]
    shown = ', '.join(f"{item['name']} ({item['accuracy']}%)" for item in matches[:2])
    return {
        'ip': ip,
        'names': names,
        'state': status.get('state', '') if status is not None else '',
        'reason': status.get('reason', '') if status is not None else '',
        'mac': mac,
        'vendor': vendor,
        'os': shown,
        'osMatches': matches,
        'ports': [_port(item, today) for item in node.findall('ports/port')],
        'scripts': [_script(item, today) for item in node.findall('hostscript/script')],
    }


def _port(node, today: date) -> dict:
    state = node.find('state')
    service = node.find('service')
    return {
        'port': node.get('portid', ''),
        'protocol': node.get('protocol', ''),
        'state': state.get('state', '') if state is not None else '',
        'reason': state.get('reason', '') if state is not None else '',
        'service': service.get('name', '') if service is not None else '',
        'product': service.get('product', '') if service is not None else '',
        'version': service.get('version', '') if service is not None else '',
        'scripts': [_script(item, today) for item in node.findall('script')],
    }


def _script(node, today: date) -> dict:
    output = node.get('output', '') or ''
    kind = script_kind(output)
    return {
        'id': node.get('id', ''),
        'kind': kind,
        'output': output.strip(),
        'note': smb_note(node.get('id', ''), output),
        'lines': cert_lines(output, today) if node.get('id') == 'ssl-cert' else [],
        'days': cert_days(output, today) if node.get('id') == 'ssl-cert' else None,
    }


def script_kind(output: str) -> str:
    """Separa vulnerabilidad informada, comprobación correcta, error e inconcluso.

    `NOT VULNERABLE` no cuenta como vulnerabilidad. Una versión de servicio no pasa por acá.
    """
    if _VULNERABLE.search(output or ''):
        return 'vulnerable'
    text = (output or '').strip().upper()
    if text.startswith('ERROR') or '\nERROR' in text:
        return 'error'
    lowered = (output or '').lower()
    if any(mark in lowered for mark in ('inconclusive', 'could not', 'unknown result', 'no reply')):
        return 'inconclusive'
    if 'NOT VULNERABLE' in text:
        return 'ok'
    return 'info'


def smb_note(script_id: str, output: str) -> str:
    text = (output or '').lower()
    if script_id == 'smb-protocols' and 'smbv1' in text.replace(' ', ''):
        return 'nmapSmbV1'
    if 'signing' not in text and 'message signing' not in text:
        return ''
    if 'not required' in text or 'disabled' in text:
        return 'nmapSmbSignOff' if 'disabled' in text else 'nmapSmbSignOptional'
    if 'required' in text:
        return 'nmapSmbSignRequired'
    return ''


def cert_lines(output: str, today: date) -> list[dict]:
    found = _cert_fields(output)
    mapping = (
        ('Subject', 'nmapCertSubject'),
        ('Issuer', 'nmapCertIssuer'),
        ('Subject Alternative Name', 'nmapCertSan'),
        ('Not valid before', 'nmapCertFrom'),
        ('Not valid after', 'nmapCertUntil'),
        ('SHA-256', 'nmapCertSha256'),
        ('SHA-1', 'nmapCertSha1'),
    )
    lines = [{'label': key, 'value': found[name]} for name, key in mapping if found.get(name)]
    days = cert_days(output, today)
    if days is not None:
        lines.append({'label': 'nmapCertDays', 'value': str(days)})
    return lines


def cert_days(output: str, today: date) -> int | None:
    raw = _cert_fields(output).get('Not valid after', '')
    expiry = _cert_date(raw)
    if expiry is None:
        return None
    return (expiry.date() - today).days


def _cert_fields(output: str) -> dict[str, str]:
    found = {}
    for line in (output or '').splitlines():
        if ':' not in line:
            continue
        name, _, value = line.partition(':')
        found.setdefault(name.strip(), value.strip())
    return found


def _cert_date(value: str) -> datetime | None:
    text = re.sub(r'\.\d+', '', (value or '').strip()).replace('Z', '+0000')
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def open_tcp_ports(hosts: tuple[dict, ...] | list[dict]) -> str:
    found = sorted({int(port['port']) for host in hosts for port in host.get('ports', [])
                    if port.get('protocol') == 'tcp' and port.get('state') == 'open' and str(port.get('port', '')).isdigit()})
    return ','.join(str(port) for port in found)


def compare_scans(before: list[dict], after: list[dict]) -> dict:
    """Diferencias entre dos informes. Un puerto `open|filtered` no se toma como abierto."""
    def up(hosts):
        return {host['ip']: host for host in hosts if host.get('ip') and host.get('state') == 'up'}

    def opened(hosts):
        found = {}
        for host in hosts:
            for port in host.get('ports', []):
                if port.get('state') == 'open':
                    found[(host['ip'], port.get('protocol', ''), port.get('port', ''))] = port
        return found

    previous, current = up(before), up(after)
    previous_ports, current_ports = opened(before), opened(after)
    changes = []
    for key in sorted(set(previous_ports) & set(current_ports)):
        old, new = _service_text(previous_ports[key]), _service_text(current_ports[key])
        if old != new:
            host, protocol, port = key
            changes.append(f'{host} {protocol}/{port}: {old or "—"} -> {new or "—"}')
    return {
        'newHosts': sorted(set(current) - set(previous)),
        'goneHosts': sorted(set(previous) - set(current)),
        'newPorts': [_port_text(key) for key in sorted(set(current_ports) - set(previous_ports))],
        'gonePorts': [_port_text(key) for key in sorted(set(previous_ports) - set(current_ports))],
        'changes': changes,
    }


def _service_text(port: dict) -> str:
    return ' '.join(part for part in (port.get('service', ''), port.get('product', ''), port.get('version', '')) if part)


def _port_text(key: tuple[str, str, str]) -> str:
    host, protocol, port = key
    return f'{host} {protocol}/{port}'
