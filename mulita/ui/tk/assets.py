from __future__ import annotations

from enum import Enum
from pathlib import Path
from tkinter import PhotoImage


class Icon(Enum):
    SHARE = 'sharethis-32.png'
    REFRESH = 'refresh-32.png'
    KEYBOARD = 'keyboard-2-32.png'
    BACK = 'arrow-81-32.png'


class Assets:
    """Rutas absolutas: la app funciona sin importar desde que carpeta se lance.
    Tk necesita que la imagen siga referenciada mientras se muestre."""

    def __init__(self, directory: Path):
        self._directory = directory
        self._cache: dict[Icon, PhotoImage] = {}

    def icon(self, icon: Icon) -> PhotoImage:
        if icon not in self._cache:
            self._cache[icon] = PhotoImage(file=str(self._directory / icon.value))
        return self._cache[icon]
