"""Ubicaciones de los programas incluidos en esta instalación."""
from pathlib import Path


def server_programs() -> Path:
    return Path(__file__).resolve().parent.parent / 'servers'
