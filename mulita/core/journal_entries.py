"""Structured daily records and portable CSV snapshots (no UI or IO)."""
import csv
import io
import json
from collections import Counter
from datetime import datetime


def entries_from(text, metadata=''):
    remaining = Counter(text.splitlines())
    grouped = {}
    for line in metadata.splitlines():
        try:
            item = json.loads(line)
            required = ('operation_id', 'timestamp', 'kind', 'phase', 'text', 'results')
            if not all(isinstance(item.get(key), str) for key in required):
                continue
            saved = item.get('lines')
            if not isinstance(saved, list) or not saved or not all(isinstance(s, str) for s in saved):
                continue
            counts = Counter(saved)
            if any(remaining[s] < n for s, n in counts.items()):
                continue  # Ignore orphaned metadata after external edits or interrupted writes.
            stamp = datetime.fromisoformat(item['timestamp'])
            remaining.subtract(counts)
            key = item['operation_id']
            if key not in grouped:
                grouped[key] = dict(date=stamp.strftime('%Y-%m-%d'), time=stamp.strftime('%H:%M:%S'),
                                    timestamp=item['timestamp'], kind=item['kind'], text='', results='', phase='started')
            entry = grouped[key]
            if item['text']:
                entry['text'] = item['text']
            if item['results']:
                entry['results'] = '\n'.join(filter(None, (entry['results'], item['results'])))
            entry['phase'] = item['phase']
        except (ValueError, TypeError, AttributeError):
            continue
    entries = list(grouped.values())
    for line in text.splitlines():
        if not remaining[line]:
            continue
        remaining[line] -= 1
        stamp, separator, body = line.partition(' - ')
        try:
            date = datetime.strptime(stamp, '%Y-%d-%m %H:%M')
            timestamp, day, clock = date.isoformat(timespec='minutes'), date.strftime('%Y-%m-%d'), date.strftime('%H:%M')
        except ValueError:
            timestamp, day, clock = '', '', ''
        entries.append(dict(timestamp=timestamp, date=day, time=clock, kind='',
                            text=body if separator and timestamp else line, results='', phase='legacy'))
    return tuple(sorted(entries, key=lambda entry: entry['timestamp'], reverse=True))


def journal_csv(entries, headers=('fecha', 'tipo de prueba', 'texto', 'resultados')):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(headers)
    for entry in reversed(entries):
        # Neutralize spreadsheet formula interpretation of untrusted network names.
        values = [entry[key] for key in ('timestamp', 'kind', 'text', 'results')]
        writer.writerow(["'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value for value in values])
    return stream.getvalue().encode('utf-8-sig')
