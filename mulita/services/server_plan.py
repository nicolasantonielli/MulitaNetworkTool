"""A prepared server command and its resource cleanup."""
from dataclasses import dataclass
from typing import Callable

@dataclass
class ServerPlan:
    argv: list[str]
    cleanup: Callable[[], None] | None = None
