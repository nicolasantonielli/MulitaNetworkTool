"""Parsers for ping data."""
from __future__ import annotations

import re
from mulita.core.models import PingReply, PingSummary


_PING_REPLY = re.compile(
    r'^(?P<size>\d+)\s+bytes from\s+(?P<source>.+?):\s+'
    r'(?:icmp_)?seq=(?P<seq>\d+)\s+ttl=(?P<ttl>\d+)\s+time=(?P<time>[\d.]+)\s*ms'
    r'(?P<extra>.*)$', re.IGNORECASE)


_PING_FAIL = re.compile(
    r'^From\s+(?P<source>\S+?):?\s+(?:icmp_)?seq=(?P<seq>\d+)\s+(?P<status>.+)$',
    re.IGNORECASE)


_PING_TARGET = re.compile(r'^---\s+(?P<target>.+?)\s+ping statistics\s+---\s*$', re.IGNORECASE)


_PING_LOSS = re.compile(
    r'(?P<tx>\d+)\s+packets transmitted,\s+(?P<rx>\d+)\s+(?:packets\s+)?received,\s+'
    r'(?:\+(?P<errors>\d+)\s+errors,\s+)?'
    r'(?P<loss>[\d.]+)%\s+packet loss(?:,\s+time\s+(?P<elapsed>\d+)ms)?',
    re.IGNORECASE)


_PING_RTT = re.compile(
    r'(?:rtt|round-trip)\s+min/avg/max(?:/mdev)?\s*=\s*'
    r'(?P<min>[\d.]+)/(?P<avg>[\d.]+)/(?P<max>[\d.]+)(?:/(?P<mdev>[\d.]+))?\s*ms',
    re.IGNORECASE)


def read_ping_line(line: str, summary: PingSummary | None = None) -> tuple[PingReply | None, PingSummary]:
    """Una linea de ping de Linux. Devuelve la respuesta, si hay, y el resumen acumulado."""
    current = summary or PingSummary()
    text = (line or '').strip()
    target = _PING_TARGET.match(text)
    if target:
        return None, _copy_summary(current, target=target.group('target'))
    loss = _PING_LOSS.search(text)
    if loss:
        return None, _copy_summary(
            current,
            transmitted=loss.group('tx'),
            received=loss.group('rx'),
            loss=f"{loss.group('loss')}%",
            elapsed=f"{loss.group('elapsed')} ms" if loss.group('elapsed') else current.elapsed,
        )
    rtt = _PING_RTT.search(text)
    if rtt:
        return None, _copy_summary(
            current,
            minimum=rtt.group('min'),
            average=rtt.group('avg'),
            maximum=rtt.group('max'),
            deviation=rtt.group('mdev') or current.deviation,
        )
    reply = _PING_REPLY.match(text)
    if reply:
        extra = reply.group('extra') or ''
        status = 'dup' if 'DUP!' in extra.upper() else 'ok'
        return PingReply(
            seq=int(reply.group('seq')),
            source=reply.group('source').strip(),
            ttl=reply.group('ttl'),
            time=reply.group('time'),
            status=status,
        ), current
    failed = _PING_FAIL.match(text)
    if failed:
        return PingReply(
            seq=int(failed.group('seq')),
            source=failed.group('source').strip(),
            ttl='',
            time='',
            status='fail',
            detail=failed.group('status').strip(),
        ), current
    return None, current


def _copy_summary(summary: PingSummary, **changes: str) -> PingSummary:
    data = {
        'target': summary.target,
        'transmitted': summary.transmitted,
        'received': summary.received,
        'loss': summary.loss,
        'elapsed': summary.elapsed,
        'minimum': summary.minimum,
        'average': summary.average,
        'maximum': summary.maximum,
        'deviation': summary.deviation,
    }
    data.update({key: value for key, value in changes.items() if value})
    return PingSummary(**data)
