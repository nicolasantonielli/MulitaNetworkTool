"""Parsers for speed data."""
from __future__ import annotations

import json
from mulita.core.errors import CommandFailedError
from mulita.core.models import SpeedTestResult


def parse_speed_test(text: str) -> SpeedTestResult:
    """Salida de `speedtest --json` (speedtest-cli), en bits por segundo."""
    try:
        data = json.loads(text)
        return SpeedTestResult(download_bps=float(data['download']), upload_bps=float(data['upload']))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise CommandFailedError('No se pudo interpretar el resultado del test de velocidad') from exc
