"""Persistence and validation of user Nmap profiles."""
from pathlib import Path
import json
import os
import tempfile
from mulita.core.errors import ValidationError, PersistenceError
from mulita.core.messages import message
from mulita.core.nmapscan import saved_arguments


class NmapProfiles:
    def __init__(self, directory: Path):
        self._state = directory

    def users(self) -> list[dict]:
        try:
            data = json.loads((self._state / 'profiles.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict) and str(item.get('id', '')).startswith('user-')]


    def save_user(self, profile_id: str, name: str, description: str, arguments: str) -> dict:
        clean = _profile_name(name)
        line = _saved_line(arguments)
        about = (description or '').strip()
        if len(about) > 240:
            raise ValidationError(message('nmapBadName'))
        items = self.users()
        if profile_id.startswith('user-') and any(item['id'] == profile_id for item in items):
            saved = {'id': profile_id, 'name': clean, 'description': about, 'arguments': line}
            items = [saved if item['id'] == profile_id else item for item in items]
        else:
            number = 1 + max((int(item['id'].split('-', 1)[1]) for item in items
                              if item['id'].split('-', 1)[-1].isdigit()), default=0)
            saved = {'id': f'user-{number}', 'name': clean, 'description': about, 'arguments': line}
            items.append(saved)
        self._write_users(items)
        return saved


    def delete_user(self, profile_id: str) -> None:
        items = [item for item in self.users() if item['id'] != profile_id]
        if len(items) == len(self.users()):
            raise ValidationError(message('nmapBadProfile', value=profile_id))
        self._write_users(items)


    def duplicate_user(self, profile_id: str) -> dict:
        source = next((item for item in self.users() if item['id'] == profile_id), None)
        if source is None:
            raise ValidationError(message('nmapBadProfile', value=profile_id))
        return self.save_user('', f"{source['name']} (copy)", source.get('description', ''),
                              source.get('arguments', ''))


    def _write_users(self, items: list[dict]) -> None:
        temporary = None
        try:
            self._state.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self._state,
                                             delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(items, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._state / 'profiles.json')
        except OSError as exc:
            raise PersistenceError(message('nmapProfilesSaveFailed')) from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


def _profile_name(name: str) -> str:
    clean = ' '.join((name or '').split())
    if not clean or len(clean) > 40:
        raise ValidationError(message('nmapBadName'))
    return clean


def _saved_line(arguments: str) -> str:
    return saved_arguments(arguments)
