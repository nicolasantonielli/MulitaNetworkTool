"""Punto de composicion: el unico lugar que conoce todas las implementaciones."""
from __future__ import annotations
from contextlib import nullcontext

import logging
import os
import sys
from pathlib import Path
from typing import Sequence

from mulita.adapters.sensors import Dht11Sensor, FixedClimateSensor
from mulita.adapters.settings_store import JsonSettingsStore
from mulita.adapters.deployment import server_programs
from mulita.adapters.backlight import PanelBacklight
from mulita.adapters.removable_storage import LinuxRemovableStorage
from mulita.adapters.switchport import LinuxPacketSource, SysfsLinkReader, JsonSwitchReportStore
from mulita.adapters.subprocess_runner import SubprocessCommandRunner
from mulita.adapters.export_bundle import export_bundle
from mulita.config import AppConfig, load_config
from mulita.core.commands import CommandFactory
from mulita.core.models import Calibration
from mulita.core.events import EventSource
from mulita.presentation.journal import render_record
from mulita.adapters.journals import FileJournalRepository
from mulita.services.journal_archive import JournalArchive
from mulita.services.journal import TechnicalJournalService
from mulita.core.ports import ClimateSensor, CommandRunner, SettingsStore, ExportBundle
from mulita.services import Services
from mulita.services.settings import SettingsService
from mulita.services.diagnostics import (DiscoveryService, PingService,
                                         PortScanService, TraceService)
from mulita.services.ethernet import EthernetService
from mulita.services.files import CaptureFilesService
from mulita.services.network import (CaptureService, InterfaceService,
                                     TapService)
from mulita.services.servers import ServerService
from mulita.services.system import (KeyboardService, MaintenanceService,
                                    ShareService)
from mulita.services.nmapscan import NmapScanService
from mulita.services.tls import TlsService
from mulita.services.switchport import SwitchPortService
from mulita.services.tools import (ClimateService, MacVendorService, PublicIpService,
                                   SpeedTestService, WakeOnLanService)
from mulita.services.wifi import WifiService
from mulita.version import __version__


def _climate(config: AppConfig) -> ClimateService:
    if config.test_mode:
        return ClimateService(FixedClimateSensor(temperature=29, humidity=78), Calibration())
    sensor: ClimateSensor = Dht11Sensor(config.sensor.pin)
    return ClimateService(sensor, Calibration(
        temperature_offset=config.sensor.temperature_offset,
        humidity_offset=config.sensor.humidity_offset))


def build_services(config: AppConfig, runner: CommandRunner | None = None,
                   climate: ClimateService | None = None,
                   settings_store: SettingsStore | None = None,
                   exporter: ExportBundle | None = None) -> Services:
    runner = runner or SubprocessCommandRunner()
    commands = CommandFactory(config.binaries, server_programs())
    capture = CaptureService(runner, commands, config.capture_dir)
    tap = TapService(runner, commands, CaptureService(runner, commands, config.storage.folder('tap')))
    settings = SettingsService(settings_store or JsonSettingsStore(config.settings_path), PanelBacklight())
    repositories = {place: FileJournalRepository(Path(config.storage.folder(place)), suffix)
                    for place, suffix in (('actividad', '.log'), ('bitacora', '.txt'))}
    archives = {place: JournalArchive(repository) for place, repository in repositories.items()}
    def flush_journals():
        for archive in archives.values():
            archive.flush()
    journal = TechnicalJournalService(settings, render_record, archives['bitacora'].append)
    services = Services(
        interfaces=InterfaceService(runner, commands),
        ethernet=EthernetService(runner, commands, config.internal_interface, config.internal_connection),
        wifi=WifiService(runner, commands, config.wifi_dir),
        capture=capture,
        tap=tap,
        trace=TraceService(runner, commands, config.trace_cycles, config.trace_dir),
        ping=PingService(runner, commands, config.ping_dir,
                         exporter=exporter if exporter is not None else export_bundle),
        port_scan=PortScanService(runner, commands, config.scan_dir),
        discovery=DiscoveryService(runner, commands, config.discovery_dir),
        wake_on_lan=WakeOnLanService(runner, commands),
        climate=climate or _climate(config),
        speed_test=SpeedTestService(runner, commands),
        public_ip=PublicIpService(
            runner, commands, config.public_ip_url, config.public_ip_timeout, config.public_ip_dir),
        mac_vendor=MacVendorService(runner, commands, config.mac_vendor_url, config.mac_vendor_timeout),
        files=CaptureFilesService(
            config.capture_dir, lambda: capture.is_running, lambda: tap.is_running,
            storage=LinuxRemovableStorage(runner, commands),
            journal_flush=lambda place: archives[place].flush() if place in archives else None,
            journal_access=lambda place: repositories[place].transaction() if place in repositories else nullcontext(),
            journal_csv=repositories['bitacora'].csv_bytes, journal_files=repositories),
        maintenance=MaintenanceService(runner, commands, config.repository_dir, config.service_name,
                                   config.update_remote, config.update_branch, config.installation_user,
                                   before_shutdown=flush_journals),
        keyboard=KeyboardService(runner, commands),
        share=ShareService(),
        settings=settings,
        journal=journal,
        journals=archives,
        servers=ServerService(runner, commands, config.servers_dir, config.servers_state_dir,
                              config.capture_dir, settings_path=config.settings_path),
        tls=TlsService(runner, commands, config.tls_dir),
        nmap=NmapScanService(runner, commands, config.nmap_dir,
                             config.settings_path.parent / 'nmap', config.capture_dir),
        switchport=SwitchPortService(LinuxPacketSource(), SysfsLinkReader(),
                                    JsonSwitchReportStore(config.storage.folder('puerto-switch'))),
    )
    for service in vars(services).values():
        if isinstance(service, EventSource):
            service.set_event_sink(journal.record)
    return services


def _ensure_home() -> None:
    """El servicio no define HOME. netdiscover lo pide aunque se use -d."""
    if os.environ.get('HOME'):
        return
    try:
        import pwd
        home = pwd.getpwuid(os.getuid()).pw_dir
    except (ImportError, KeyError, OSError, AttributeError):
        return
    if home:
        os.environ['HOME'] = home


def main(argv: Sequence[str] | None = None) -> None:
    _ensure_home()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    config = load_config(sys.argv[1:] if argv is None else argv)
    logging.getLogger(__name__).info('Mulita %s', __version__)
    services = build_services(config)

    from mulita.ui.qt.app import QtApplication
    sys.exit(QtApplication(config, services).run())
