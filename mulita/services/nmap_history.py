"""Read saved Nmap runs and compare their XML results."""
from datetime import date
from pathlib import Path
import json
import re
from mulita.core.errors import ValidationError
from mulita.core.messages import message
from mulita.core.nmapscan import parse_xml, compare_scans

_RUN = re.compile(r'^[0-9]{8}-[0-9]{6}(?:-\d+)?$')


class NmapHistory:
    def __init__(self, directory: Path):
        self._directory = directory

    def load(self, run_id: str, today: date | None = None) -> tuple[dict, tuple[dict, ...]]:
        folder = self._folder(run_id)
        meta = self.read_meta(folder)
        document = parse_xml(self.read_text(folder / 'informe.xml'), today or date.today())
        return meta, document.hosts


    def compare(self, first: str, second: str, today: date | None = None) -> dict:
        _meta, before = self.load(first, today)
        _other, after = self.load(second, today)
        return compare_scans(list(before), list(after))


    def history(self, active: Path | None = None) -> list[dict]:
        if not self._directory.is_dir():
            return []
        found = []
        for child in self._directory.iterdir():
            if not child.is_dir() or not (child / 'meta.json').is_file():
                continue
            item = self.read_meta(child)
            if item.get('status') == 'running' and child != active:
                item['status'] = 'incomplete'
            found.append({key: item.get(key, '') for key in (
                'id', 'profile', 'command', 'targets', 'started', 'finished', 'status',
                'partial', 'simulated', 'nmapVersion')})
        found.sort(key=lambda item: item.get('started', ''), reverse=True)
        return found[:40]


    def _folder(self, run_id: str) -> Path:
        if not _RUN.fullmatch(run_id or ''):
            raise ValidationError(message('nmapRunMissing'))
        folder = self._directory / run_id
        if not folder.is_dir() or folder.parent.resolve() != self._directory.resolve():
            raise ValidationError(message('nmapRunMissing'))
        return folder


    def read_meta(self, folder: Path) -> dict:
        try:
            data = json.loads((folder / 'meta.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {'id': folder.name}
        return data if isinstance(data, dict) else {'id': folder.name}


    @staticmethod
    def read_text(path: Path) -> str:
        try:
            return path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return ''
