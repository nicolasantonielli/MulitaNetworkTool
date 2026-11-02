"""Descubrimiento y montaje USB de la plataforma Linux."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path, PurePosixPath
from mulita.core.commands import CommandFactory
from mulita.core.ports import CommandRunner
from mulita.core.platform import UsbDrive
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.messages import message

_DEVICE = re.compile(r'^[A-Za-z0-9]+$')
_USB_BUS = re.compile(r'usb\d+')
_PARTITION = re.compile(r'p\d+$')
_TRAILING_INDEX = re.compile(r'\d+$')
_MOUNT_ROOT = Path('/mnt/mulita-usb')
_SYSTEM_MOUNTS = {'/', '/boot', '/boot/firmware'}

class LinuxRemovableStorage:
    def __init__(self, runner: CommandRunner, commands: CommandFactory):
        self._runner = runner
        self._commands = commands

    def sync(self) -> None:
        if hasattr(os, 'sync'):
            os.sync()

    def list_drives(self) -> tuple[UsbDrive, ...]:
        listed = self._from_lsblk()
        if listed:
            return listed
        sysfs = list_usb_drives()
        return sysfs or listed or ()

    def _from_lsblk(self) -> tuple[UsbDrive, ...] | None:
        if self._runner is None or self._commands is None:
            return None
        result = self._runner.run(self._commands.usb_block_devices())
        if not result.ok:
            return None
        return parse_usb_drives(result.text)

    def folder(self, drive_id: str) -> Path:
        if not _DEVICE.fullmatch(drive_id or ""):
            raise ValidationError(message("badDrive"))
        drives = {item.device: item for item in self.list_drives()}
        drive = drives.get(drive_id)
        if drive is None:
            raise ValidationError(message('usbMissing'))
        mounted = drive.mountpoint or _mount_points().get(f'/dev/{drive_id}', '')
        if mounted:
            folder = Path(mounted)
            if not folder.is_dir():
                raise ValidationError(message('usbUnusable'))
            return folder
        if self._runner is None or self._commands is None or os.name != 'posix':
            raise ValidationError(message('usbUnusable'))
        target = _MOUNT_ROOT / drive_id
        target.mkdir(parents=True, exist_ok=True)
        result = self._runner.run(self._commands.mount_partition(drive_id, str(target)))
        if not result.ok:
            raise CommandFailedError('No se pudo preparar el pendrive', result)
        return target


def parse_usb_drives(text: str) -> tuple[UsbDrive, ...]:
    """Discos con transporte usb. No exige que esten montados."""
    try:
        payload = json.loads(text or '')
    except json.JSONDecodeError:
        return ()
    found: list[UsbDrive] = []
    for disk in payload.get('blockdevices') or []:
        if not isinstance(disk, dict) or disk.get('tran') != 'usb' or _holds_system(disk):
            continue
        for node in _filesystem_nodes(disk):
            name = str(node.get('name') or '')
            if not _DEVICE.fullmatch(name):
                continue
            found.append(UsbDrive(name, _node_label(node), _node_mount(node)))
    return tuple(found)


def list_usb_drives(block: Path | None = None, mounts_file: Path | None = None) -> tuple[UsbDrive, ...]:
    """Particiones USB. En la PC de desarrollo no hay /sys/block."""
    block = block or Path('/sys/block')
    if not block.is_dir():
        return ()
    mounts = _mount_points(mounts_file)
    system = _system_disks(mounts)
    found: list[UsbDrive] = []
    for device in block.iterdir():
        if device.name in system or not _usb_disk(device):
            continue
        parts = [child for child in device.iterdir()
                 if child.is_dir() and child.name.startswith(device.name) and _DEVICE.fullmatch(child.name)]
        nodes = parts or ([device] if _DEVICE.fullmatch(device.name) else [])
        for node in nodes:
            dev = f'/dev/{node.name}'
            found.append(UsbDrive(node.name, _volume_label(dev) or 'Pendrive', mounts.get(dev, '')))
    return tuple(found)


def _filesystem_nodes(disk: dict) -> list[dict]:
    children = [child for child in disk.get('children') or [] if isinstance(child, dict)]
    if not children:
        return [disk]
    nodes: list[dict] = []
    for child in children:
        nodes.extend(_filesystem_nodes(child))
    return nodes


def _holds_system(node: dict) -> bool:
    if _node_mount(node) in _SYSTEM_MOUNTS:
        return True
    return any(_holds_system(child) for child in node.get('children') or [] if isinstance(child, dict))


def _node_label(node: dict) -> str:
    label = node.get('label')
    if isinstance(label, str) and label.strip():
        return label.strip()
    return 'Pendrive'


def _node_mount(node: dict) -> str:
    point = node.get('mountpoint')
    if isinstance(point, str) and point:
        return point
    points = node.get('mountpoints') or []
    if isinstance(points, list):
        for item in points:
            if isinstance(item, str) and item:
                return item
    return ''


def _usb_disk(device: Path) -> bool:
    """El pendrive entra como disco SCSI. El bus usb queda en la ruta real, no en subsystem."""
    link = device / 'device'
    try:
        resolved = link.resolve().as_posix()
    except OSError:
        return False
    return any(_USB_BUS.fullmatch(part) for part in PurePosixPath(resolved).parts)


def _system_disks(mounts: dict[str, str]) -> set[str]:
    disks: set[str] = set()
    for device, point in mounts.items():
        if point in _SYSTEM_MOUNTS:
            name = _disk_name(device)
            if name:
                disks.add(name)
    return disks


def _disk_name(device: str) -> str:
    name = PurePosixPath(device).name
    if name == 'root':
        try:
            name = Path('/dev/root').resolve().name
        except OSError:
            return ''
    if _PARTITION.search(name):
        return _PARTITION.sub('', name)
    return _TRAILING_INDEX.sub('', name) or name


def _mount_points(mounts_file: Path | None = None) -> dict[str, str]:
    mounts = mounts_file or Path('/proc/mounts')
    if not mounts.is_file():
        return {}
    found = {}
    for line in mounts.read_text(encoding='utf-8', errors='replace').splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith('/dev/'):
            found[parts[0]] = parts[1].replace('\\040', ' ')
    return found


def _volume_label(device: str) -> str:
    folder = Path('/dev/disk/by-label')
    if not folder.is_dir():
        return ''
    try:
        target = Path(device).resolve()
    except OSError:
        return ''
    for entry in folder.iterdir():
        try:
            if entry.resolve() == target:
                return entry.name.replace('\\x20', ' ')
        except OSError:
            continue
    return ''


