"""Identificadores y rutas compartidos; cada consumidor conserva sus filtros."""
from dataclasses import dataclass
from pathlib import PurePath


@dataclass(frozen=True)
class StoragePlace:
    id: str
    folder: str
    label: str
    suffixes: tuple[str, ...] = ()
    nmap_input: bool = True


PLACES = (
    StoragePlace('captura', '', 'placeCapture', ('.pcap',)),
    StoragePlace('tap', 'tap', 'placeTap', ('.pcap',)),
    StoragePlace('traza', 'trazas', 'placeTrace', ('.csv',)),
    StoragePlace('ping', 'ping', 'placePing', ('.csv',)),
    StoragePlace('publica', 'internet', 'placePublic', ('.csv',)),
    StoragePlace('wifi', 'wifi', 'placeWifi', ('.csv',)),
    StoragePlace('escaneo', 'escaneo', 'placeScan', ('.csv',)),
    StoragePlace('descubrimiento', 'descubrimiento', 'placeDiscover', ('.csv',)),
    StoragePlace('tls', 'tls', 'placeTls', ('.csv',)),
    StoragePlace('puerto-switch', 'puerto-switch', 'switchTitle', ('.json',), False),
    StoragePlace('actividad', 'actividad', 'activityTitle', ('.log',), False),
    StoragePlace('servidores', 'servidores', 'pageServers'),
    StoragePlace('nmap', 'nmap', 'cyberNmap'),
)


@dataclass(frozen=True)
class StoragePaths:
    root: PurePath

    def folder(self, place: str) -> PurePath:
        for item in PLACES:
            if item.id == place:
                return self.root / item.folder if item.folder else self.root
        raise KeyError(place)
