"""Compilacion de las opciones de la pantalla a un comando Nmap seguro."""
from __future__ import annotations

import ipaddress
import re
import shlex
from dataclasses import dataclass, field
from typing import Callable

from mulita.core import validation
from mulita.core.errors import ValidationError
from mulita.core.messages import message
from mulita.core.nmap_catalog import Profile, _CHECK_IDS, profile_by_id

Resolver = Callable[[str], str | None]

_PRIVILEGE = ('requires root', 'raw socket', 'raw sockets', 'privileges')

_FILE_OPTIONS = {'-iL', '--excludefile', '--script-args-file'}

_TAKES_VALUE = {
    '-p', '--top-ports', '-e', '--exclude', '--script', '--script-args', '-iL', '--excludefile',
    '--stats-every', '--version-intensity', '-S', '-g', '--source-port', '-D', '--data',
    '--data-string', '--data-length', '--stylesheet', '--datadir', '--servicedb', '--versiondb',
    '--script-timeout', '--dns-servers', '--proxies', '-oN', '-oX', '-oG', '-oA', '-oS',
    '--max-retries', '--host-timeout', '--min-rate', '--max-rate', '--min-parallelism',
    '--max-parallelism', '--max-rtt-timeout', '--min-rtt-timeout', '--initial-rtt-timeout',
    '--scan-delay', '--max-scan-delay', '--min-hostgroup', '--max-hostgroup',
    '--script-args-file', '--script-help', '--scanflags', '--exclude-ports',
    '--mtu', '--ttl', '--spoof-mac', '--ip-options', '--resume', '--port-ratio',
    '--max-os-tries', '-iR', '-sI', '-b', '-T',
}

_FORBIDDEN = {'-oN', '-oX', '-oG', '-oA', '-oS', '--append-output'}

_TIMING_FLAG = re.compile(r'^-T[0-5]$')

_SCRIPT = re.compile(r'^[A-Za-z0-9_.-]+$')

_PORT = re.compile(r'^\d{1,5}(?:-\d{1,5})?(?:,\d{1,5}(?:-\d{1,5})?)*$')

_RANGE = re.compile(r'^(\d{1,3}(?:\.\d{1,3}){3})-(\d{1,3})$')

_HOST = re.compile(
    r'^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)'
    r'(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$')

_TIMING = {'T2', 'T3', 'T4'}


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
        raise ValidationError(message('nmapBadTiming', value=timing))
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
        notes.append(message('nmapPnWarn'))
    notes.append(message('nmapReportsNote'))
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
    scripts: list[str] = []
    listed = False
    index = 0
    while index < len(parsed):
        token = parsed[index]
        _reject_output_option(token)
        option, separator, attached = token.partition('=')
        if separator and option in _TAKES_VALUE:
            shown, real = _resolve_option(option, attached, resolve_file)
            display.append(option + '=' + shown)
            resolved.append(option + '=' + real)
            if option == '--script':
                scripts.extend(real.split(','))
            listed = listed or option == '-iL'
            index += 1
            continue
        if token in _TAKES_VALUE:
            if index + 1 >= len(parsed):
                raise ValidationError(message('nmapOptionNeedsValue', option=token))
            value = parsed[index + 1]
            _reject_output_option(token)
            shown, real = _resolve_option(token, value, resolve_file)
            display.extend([token, shown])
            resolved.extend([token, real])
            if token == '--script':
                scripts.extend(real.split(','))
            listed = listed or token == '-iL'
            index += 2
            continue
        if token.startswith('-'):
            display.append(token)
            resolved.append(token)
            if token in ('-sC', '-A'):
                scripts.append('default')
            index += 1
            continue
        inline_targets.append(_one_target(token))
        index += 1
    if inline_targets:
        notes.append(message('nmapTargetInLine'))
        targets = inline_targets
    elif listed:
        notes.append(message('nmapTargetInFile'))
        targets = []
    else:
        targets = parse_targets(targets_field)
        notes.append(message('nmapTargetInField'))
    _runtime_flags(resolved)
    _runtime_flags(display)
    return Compiled('custom', '', resolved + targets, display + targets, len(targets),
                    scripts=tuple(dict.fromkeys(scripts)))


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
        raise ValidationError(message('nmapNeedArgs'))
    try:
        args = shlex.split(text, posix=True)
    except ValueError as exc:
        raise ValidationError(message('nmapBadArgs', value=exc)) from exc
    if not args:
        raise ValidationError(message('nmapNeedArgs'))
    return args


def parse_targets(text: str) -> list[str]:
    tokens = (text or '').split()
    if not tokens:
        raise ValidationError(message('nmapNeedTarget'))
    return [_one_target(token) for token in tokens]


def parse_ports(text: str) -> str:
    value = (text or '').replace(' ', '')
    if not value or not _PORT.fullmatch(value):
        raise ValidationError(message('nmapBadPort', value=value or message('empty')))
    for part in value.split(','):
        if '-' in part:
            start, end = (int(piece) for piece in part.split('-', 1))
            if not 1 <= start <= end <= 65535:
                raise ValidationError(message('nmapBadPort', value=part))
        elif not 1 <= int(part) <= 65535:
            raise ValidationError(message('nmapBadPort', value=part))
    return value


def privilege_error(text: str) -> bool:
    lowered = (text or '').lower()
    return any(mark in lowered for mark in _PRIVILEGE)


def _one_target(token: str) -> str:
    if token.startswith('-') or any(char in token for char in ';&|$`<>\'"\\'):
        raise ValidationError(message('nmapBadTarget', value=token))
    if '/' in token:
        try:
            ipaddress.ip_network(token, strict=False)
        except ValueError:
            raise ValidationError(message('nmapBadTarget', value=token)) from None
        return token
    if ':' in token:
        try:
            ipaddress.ip_address(token.split('%', 1)[0])
        except ValueError:
            raise ValidationError(message('nmapBadTarget', value=token)) from None
        return token
    ranged = _RANGE.fullmatch(token)
    if ranged:
        try:
            ipaddress.ip_address(ranged.group(1))
        except ValueError:
            raise ValidationError(message('nmapBadTarget', value=token)) from None
        start = int(ranged.group(1).rsplit('.', 1)[1])
        end = int(ranged.group(2))
        if not 0 <= end <= 255 or start > end:
            raise ValidationError(message('nmapBadTarget', value=token))
        return token
    try:
        ipaddress.ip_address(token)
        return token
    except ValueError:
        pass
    if _HOST.fullmatch(token):
        return token
    raise ValidationError(message('nmapBadTarget', value=token))


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
            raise ValidationError(message('nmapBadUdp', value=mode))
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
        raise ValidationError(message('nmapNeedScript'))
    names = []
    for item in chosen:
        name = str(item)
        if name not in _CHECK_IDS:
            raise ValidationError(message('nmapBadScript', value=name))
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
            raise ValidationError(message('nmapNeedIface'))
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
    if not any(arg == '--stats-every' or arg.startswith('--stats-every=') for arg in args):
        front.extend(['--stats-every', '5s'])
    args[:0] = front


def _reject_output_option(token: str) -> None:
    if token in _FORBIDDEN or token.startswith(('-oN', '-oX', '-oG', '-oA', '-oS')):
        raise ValidationError(message('nmapOutputManaged'))


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
                raise ValidationError(message('nmapBadScript', value=name or message('empty')))
            else:
                shown.append(name)
                real.append(name)
        if not shown:
            raise ValidationError(message('nmapNeedScript'))
        return ','.join(shown), ','.join(real)
    return value, value


def _existing_file(value: str, resolve_file: Resolver) -> str:
    resolved = resolve_file(value)
    if not resolved:
        raise ValidationError(message('nmapBadFile', name=value))
    return resolved
