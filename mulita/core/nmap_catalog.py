"""Perfiles de escaneo Nmap y chequeos de scripts disponibles."""
from __future__ import annotations

from dataclasses import dataclass

from mulita.core.errors import ValidationError
from mulita.core.messages import message

HTTP_PORTS = '80,443,8080,8443'

TLS_PORTS = '443,465,636,853,993,995,8443'


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
        raise ValidationError(message('nmapBadProfile', value=profile_id or message('empty'))) from None


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
