"""Parsers for lookup data."""
from __future__ import annotations

import ipaddress
import json
import re
from mulita.core.errors import CommandFailedError
from mulita.core.messages import message
from mulita.core.models import PublicAddress


def parse_mac_vendor(text: str) -> str:
    """Cuerpo y codigo HTTP de `curl -w '\\n%{http_code}'` contra MACVendors."""
    body, separator, code = (text or '').rpartition('\n')
    if not separator:
        raise CommandFailedError(message('vendorFail'))
    try:
        status = int(code.strip())
    except ValueError as exc:
        raise CommandFailedError(message('vendorFail')) from exc
    name = body.strip()
    if status == 200 and name:
        return name
    if status == 404:
        raise CommandFailedError(message('vendorMiss'))
    if status == 429:
        raise CommandFailedError(message('vendorLimit'))
    raise CommandFailedError(message('vendorStatus', status=status))


def parse_public_address(text: str) -> PublicAddress:
    """JSON de ipwho.is, o una sola linea con la direccion."""
    body = (text or '').strip()
    if not body:
        raise CommandFailedError(message('pubFail'))
    if not body.startswith('{'):
        address = body.splitlines()[0].strip()
        if not _ip_text(address):
            raise CommandFailedError(message('pubFail'))
        return PublicAddress(ip=address, version=_ip_version(address))
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise CommandFailedError(message('pubFail')) from exc
    if not isinstance(data, dict) or data.get('success') is False or not data.get('ip'):
        raise CommandFailedError(message('pubFail'))
    connection = data.get('connection') if isinstance(data.get('connection'), dict) else {}
    zone = data.get('timezone') if isinstance(data.get('timezone'), dict) else {}
    asn = connection.get('asn')
    asn_text = f'AS{asn}' if isinstance(asn, int) or (isinstance(asn, str) and asn.isdigit()) else _text(asn)
    country = _text(data.get('country'))
    code = _text(data.get('country_code'))
    if country and code:
        country = f'{country} ({code})'
    utc = _text(zone.get('utc'))
    zone_id = _text(zone.get('id'))
    if zone_id and utc:
        zone_id = f'{zone_id} (UTC{utc})'
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    coordinates = ''
    if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
        coordinates = f'{latitude:.4f}, {longitude:.4f}'
    address = _text(data.get('ip'))
    return PublicAddress(
        ip=address,
        version=_text(data.get('type')) or _ip_version(address),
        asn=asn_text,
        organization=_text(connection.get('org')),
        isp=_text(connection.get('isp')),
        domain=_text(connection.get('domain')),
        country=country,
        region=_text(data.get('region')),
        city=_text(data.get('city')),
        coordinates=coordinates,
        timezone=zone_id,
    )


def _text(value) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _ip_text(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _ip_version(value: str) -> str:
    try:
        return f'IPv{ipaddress.ip_address(value).version}'
    except ValueError:
        return ''
