from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from mulita.core.ports import SettingsStore
from mulita.core.errors import CommandFailedError
from mulita.core.messages import message
from mulita.core.settings import Settings, settings_from_dict

log = logging.getLogger(__name__)


class JsonSettingsStore(SettingsStore):

    def __init__(self, path: Path):
        self._path = path

    def load(self) -> Settings:
        try:
            data = json.loads(self._path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return Settings()
        except (OSError, json.JSONDecodeError) as exc:
            log.warning('Preferencias ilegibles en %s: %s', self._path, exc)
            return Settings()
        return settings_from_dict(data if isinstance(data, dict) else {})

    def save(self, settings: Settings) -> None:
        """Escritura atomica: un corte de luz no deja el archivo a medias."""
        temporary = self._path.with_suffix('.tmp')
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(settings.to_dict(), indent=2), encoding='utf-8')
            os.replace(temporary, self._path)
        except OSError as exc:
            raise CommandFailedError(message('settingsSaveFailed')) from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


class MemorySettingsStore(SettingsStore):

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    def load(self) -> Settings:
        return self.settings

    def save(self, settings: Settings) -> None:
        self.settings = settings
