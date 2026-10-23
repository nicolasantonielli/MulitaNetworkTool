from __future__ import annotations

from dataclasses import dataclass

from mulita.services.diagnostics import (DiscoveryService, PingService,
                                         PortScanService, TraceService)
from mulita.services.network import (CaptureService, InterfaceService,
                                     TapService)
from mulita.services.settings import SettingsService
from mulita.services.system import (KeyboardService, MaintenanceService,
                                    ShareService)
from mulita.services.tools import (ClimateService, PublicIpService,
                                   SpeedTestService, WakeOnLanService)


@dataclass
class Services:
    interfaces: InterfaceService
    capture: CaptureService
    tap: TapService
    trace: TraceService
    ping: PingService
    port_scan: PortScanService
    discovery: DiscoveryService
    wake_on_lan: WakeOnLanService
    climate: ClimateService
    speed_test: SpeedTestService
    public_ip: PublicIpService
    maintenance: MaintenanceService
    keyboard: KeyboardService
    share: ShareService
    settings: SettingsService

    def shutdown(self) -> None:
        """Al cerrar la aplicacion no quedan capturas ni pings huerfanos."""
        for session in (self.capture, self.ping, self.discovery):
            session.stop()
        self.tap.stop()
        self.keyboard.hide()
