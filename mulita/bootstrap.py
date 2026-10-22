"""Punto de composicion: el unico lugar que conoce todas las implementaciones."""
from __future__ import annotations

import logging
import sys
from typing import Sequence

from mulita.adapters.sensors import Dht11Sensor, FixedClimateSensor
from mulita.adapters.subprocess_runner import SubprocessCommandRunner
from mulita.config import AppConfig, load_config
from mulita.core.commands import CommandFactory
from mulita.core.models import Calibration
from mulita.core.ports import ClimateSensor, CommandRunner
from mulita.services import Services
from mulita.services.diagnostics import (DiscoveryService, PingService,
                                         PortScanService, TraceService)
from mulita.services.network import (CaptureService, InterfaceService,
                                     TapService)
from mulita.services.system import (KeyboardService, MaintenanceService,
                                    ShareService)
from mulita.services.tools import (ClimateService, PublicIpService,
                                   SpeedTestService, WakeOnLanService)
from mulita.version import __version__


def _climate(config: AppConfig) -> ClimateService:
    if config.test_mode:
        return ClimateService(FixedClimateSensor(temperature=29, humidity=78), Calibration())
    sensor: ClimateSensor = Dht11Sensor(config.sensor.pin)
    return ClimateService(sensor, Calibration(
        temperature_offset=config.sensor.temperature_offset,
        humidity_offset=config.sensor.humidity_offset))


def build_services(config: AppConfig, runner: CommandRunner | None = None,
                   climate: ClimateService | None = None) -> Services:
    runner = runner or SubprocessCommandRunner()
    commands = CommandFactory(config.binaries)
    return Services(
        interfaces=InterfaceService(runner, commands),
        capture=CaptureService(runner, commands, config.capture_dir),
        tap=TapService(),
        trace=TraceService(runner, commands, config.trace_cycles),
        ping=PingService(runner, commands),
        port_scan=PortScanService(runner, commands),
        discovery=DiscoveryService(runner, commands),
        wake_on_lan=WakeOnLanService(runner, commands),
        climate=climate or _climate(config),
        speed_test=SpeedTestService(runner, commands),
        public_ip=PublicIpService(runner, commands, config.public_ip_url, config.public_ip_timeout),
        maintenance=MaintenanceService(runner, commands, config.repository_dir, config.reset_script),
        keyboard=KeyboardService(runner, commands),
        share=ShareService(),
    )


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    config = load_config(sys.argv[1:] if argv is None else argv)
    logging.getLogger(__name__).info('Mulita %s', __version__)
    services = build_services(config)

    from mulita.ui.tk.app import TkApplication
    TkApplication(config, services).run()
