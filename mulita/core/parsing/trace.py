"""Parsers for trace data."""
from __future__ import annotations

import csv
import io
from mulita.core.models import TraceHop
import re

_TRACE_HOP = re.compile(
    r'^\s*(?P<hop>\d+)\.\s*(?:\|--\s*)?(?P<address>\S+)\s+'
    r'(?P<loss>\d+(?:\.\d+)?)%?\s+'
    r'(?P<sent>\d+)\s+'
    r'(?P<last>\S+)\s+(?P<average>\S+)\s+(?P<best>\S+)\s+'
    r'(?P<worst>\S+)\s+(?P<deviation>\S+)\s*$')


def parse_trace(text: str) -> tuple[TraceHop, ...]:
    """Informe de mtr, en CSV o en el cuadro de texto del reporte."""
    if 'Mtr_Version' in (text or ''):
        return _parse_trace_csv(text)
    return _parse_trace_report(text)


def _parse_trace_csv(text: str) -> tuple[TraceHop, ...]:
    rows = list(csv.reader(io.StringIO(text or '')))
    header_at = next((index for index, row in enumerate(rows)
                      if row and row[0].strip() == 'Mtr_Version'), None)
    if header_at is None:
        return ()
    header = [cell.strip().lower() for cell in rows[header_at]]
    hop_at = _trace_column(header, 'hop')
    address_at = _trace_column(header, 'ip')
    if hop_at is None or address_at is None:
        return ()
    loss_at = _trace_column(header, 'loss%', 'loss')
    sent_at = _trace_column(header, 'snt')
    last_at = _trace_column(header, 'last')
    average_at = _trace_column(header, 'avg')
    best_at = _trace_column(header, 'best')
    worst_at = _trace_column(header, 'wrst', 'worst')
    deviation_at = _trace_column(header, 'stdev', 'jitter')
    hops: list[TraceHop] = []
    for row in rows[header_at + 1:]:
        if not row or row[0].strip() == 'Mtr_Version':
            continue
        hop = _trace_cell(row, hop_at)
        if not hop.isdigit():
            continue
        hops.append(TraceHop(
            hop=int(hop),
            address=_trace_cell(row, address_at) or '???',
            loss=_trace_loss(_trace_cell(row, loss_at)),
            sent=_trace_cell(row, sent_at),
            last=_trace_cell(row, last_at),
            average=_trace_cell(row, average_at),
            best=_trace_cell(row, best_at),
            worst=_trace_cell(row, worst_at),
            deviation=_trace_cell(row, deviation_at),
        ))
    return tuple(hops)


def _parse_trace_report(text: str) -> tuple[TraceHop, ...]:
    hops: list[TraceHop] = []
    for line in (text or '').splitlines():
        match = _TRACE_HOP.match(line)
        if not match:
            continue
        hops.append(TraceHop(
            hop=int(match.group('hop')),
            address=match.group('address'),
            loss=_trace_loss(match.group('loss')),
            sent=match.group('sent'),
            last=match.group('last'),
            average=match.group('average'),
            best=match.group('best'),
            worst=match.group('worst'),
            deviation=match.group('deviation'),
        ))
    return tuple(hops)


def _trace_column(header: list[str], *names: str) -> int | None:
    for name in names:
        if name in header:
            return header.index(name)
    return None


def _trace_cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ''
    return row[index].strip()


def _trace_loss(value: str) -> str:
    text = (value or '').strip()
    if not text or text.endswith('%'):
        return text
    return text + '%'
