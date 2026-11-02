"""Presentación TLS con traducción explícita, independiente del análisis del dominio."""
from mulita.core.tls import TlsFinding, SECTIONS
from mulita.presentation.i18n import Translator

_SECTION_KEYS = {
    'certificate': 'tlsSecCertificate',
    'protocols': 'tlsSecProtocols',
    'ciphers': 'tlsSecCiphers',
    'vulnerabilities': 'tlsSecVulns',
    'other': 'tlsSecOther',
}


_SEVERITY_KEYS = {
    'CRITICAL': 'tlsSevCritical',
    'HIGH': 'tlsSevHigh',
    'MEDIUM': 'tlsSevMedium',
    'LOW': 'tlsSevLow',
    'WARN': 'tlsSevWarn',
    'OK': 'tlsSevOk',
    'INFO': 'tlsSevInfo',
}


_TONES = {
    'CRITICAL': 'danger', 'HIGH': 'danger',
    'MEDIUM': 'warning', 'LOW': 'warning', 'WARN': 'warning',
    'OK': 'success',
}


_COUNTED = ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'WARN', 'OK')


_PROTOCOLS = {
    'SSLv2': 'SSL 2.0', 'SSLv3': 'SSL 3.0', 'TLS1': 'TLS 1.0',
    'TLS1_1': 'TLS 1.1', 'TLS1_2': 'TLS 1.2', 'TLS1_3': 'TLS 1.3',
}


_CERT_LABELS = {
    'cert_commonName': 'tlsIdCommonName',
    'cert_subjectAltName': 'tlsIdAltNames',
    'cert_caIssuers': 'tlsIdIssuer',
    'cert_notBefore': 'tlsIdNotBefore',
    'cert_notAfter': 'tlsIdNotAfter',
    'cert_expirationStatus': 'tlsIdExpiry',
    'cert_validityPeriod': 'tlsIdValidity',
    'cert_signatureAlgorithm': 'tlsIdSignature',
    'cert_keySize': 'tlsIdKeySize',
    'cert_trust': 'tlsIdTrust',
    'cert_chain_of_trust': 'tlsIdChain',
    'chain_of_trust': 'tlsIdChain',
    'cert_serialNumber': 'tlsIdSerial',
    'cert_fingerprintSHA256': 'tlsIdSha256',
    'cert_fingerprintSHA1': 'tlsIdSha1',
    'OCSP_stapling': 'tlsIdOcsp',
    'DNS_CAA': 'tlsIdCaa',
    'certificate_transparency': 'tlsIdTransparency',
}


def tone_of(severity: str) -> str:
    return _TONES.get(severity, 'muted')


def severity_label(severity: str, translator: Translator | None = None) -> str:
    translate = (translator or Translator()).tr
    key = _SEVERITY_KEYS.get(severity)
    return translate(key) if key else severity


def section_label(section: str, translator: Translator | None = None) -> str:
    translate = (translator or Translator()).tr
    return translate(_SECTION_KEYS.get(section, 'tlsSecOther'))


def test_label(finding: TlsFinding, translator: Translator | None = None) -> str:
    translate = (translator or Translator()).tr
    key = _CERT_LABELS.get(finding.id)
    label = translate(key) if key else _PROTOCOLS.get(finding.id, finding.id)
    return f'{label} #{finding.copy}' if finding.copy else label


def summarize(findings: tuple[TlsFinding, ...], translator: Translator | None = None) -> list[dict]:
    counts = {severity: 0 for severity in _COUNTED}
    for item in findings:
        if item.severity in counts:
            counts[item.severity] += 1
    return [{'severity': severity, 'label': severity_label(severity, translator),
             'tone': tone_of(severity), 'count': counts[severity]}
            for severity in _COUNTED if counts[severity]]


def grouped(findings: tuple[TlsFinding, ...], translator: Translator | None = None) -> list[dict]:
    """Filas para la tabla: un encabezado por sección y sus hallazgos debajo."""
    rows: list[dict] = []
    for section in SECTIONS:
        items = [item for item in findings if item.section == section]
        if not items:
            continue
        rows.append({'header': True, 'title': section_label(section, translator)})
        for item in items:
            rows.append({
                'header': False,
                'severity': severity_label(item.severity, translator),
                'tone': tone_of(item.severity),
                'test': test_label(item, translator),
                'result': item.text + (f'  ({item.cve})' if item.cve else ''),
            })
    return rows

