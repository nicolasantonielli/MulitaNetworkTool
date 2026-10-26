"""Punto de composicion: el unico lugar que conoce todas las implementaciones."""
from __future__ import annotations

import logging
import os
import sys
from typing import Sequence

from mulita.adapters.sensors import Dht11Sensor, FixedClimateSensor
from mulita.adapters.settings_store import JsonSettingsStore
from mulita.adapters.subprocess_runner import SubprocessCommandRunner
from mulita.config import AppConfig, Toolkit, load_config
from mulita.core.commands import CommandFactory
from mulita.core.models import Calibration
from mulita.core.ports import ClimateSensor, CommandRunner, SettingsStore
from mulita.services import Services
from mulita.services.settings import SettingsService
from mulita.services.diagnostics import (DiscoveryService, PingService,
                                         PortScanService, TraceService)
from mulita.services.ethernet import EthernetService
from mulita.services.network import (CaptureService, InterfaceService,
                                     TapService)
from mulita.services.system import (KeyboardService, MaintenanceService,
                                    ShareService)
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
                   settings_store: SettingsStore | None = None) -> Services:
    runner = runner or SubprocessCommandRunner()
    commands = CommandFactory(config.binaries)
    return Services(
        interfaces=InterfaceService(runner, commands),
        ethernet=EthernetService(runner, commands, config.internal_interface, config.internal_connection),
        wifi=WifiService(runner, commands),
        capture=CaptureService(runner, commands, config.capture_dir),
        tap=TapService(runner, commands, CaptureService(runner, commands, config.capture_dir / 'tap')),
        trace=TraceService(runner, commands, config.trace_cycles),
        ping=PingService(runner, commands),
        port_scan=PortScanService(runner, commands),
        discovery=DiscoveryService(runner, commands),
        wake_on_lan=WakeOnLanService(runner, commands),
        climate=climate or _climate(config),
        speed_test=SpeedTestService(runner, commands),
        public_ip=PublicIpService(runner, commands, config.public_ip_url, config.public_ip_timeout),
        mac_vendor=MacVendorService(runner, commands, config.mac_vendor_url, config.mac_vendor_timeout),
        maintenance=MaintenanceService(runner, commands, config.repository_dir, config.service_name,
                                   config.update_remote, config.update_branch),
        keyboard=KeyboardService(runner, commands),
        share=ShareService(),
        settings=SettingsService(settings_store or JsonSettingsStore(config.settings_path)),
    )


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

    if config.toolkit == Toolkit.TK:
        from mulita.ui.tk.app import TkApplication
        TkApplication(config, services).run()
    else:
        from mulita.ui.qt.app import QtApplication
        sys.exit(QtApplication(config, services).run())
