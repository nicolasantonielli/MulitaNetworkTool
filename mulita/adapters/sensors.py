from __future__ import annotations

import logging

from mulita.core.models import ClimateReading
from mulita.core.ports import ClimateSensor

log = logging.getLogger(__name__)


class Dht11Sensor(ClimateSensor):

    def __init__(self, pin: int):
        self._pin = pin
        self._driver = None
        self._sensor = None
        try:
            import Adafruit_DHT
        except ImportError:
            log.warning('Adafruit_DHT no esta instalado; el DHT11 no va a leer')
            return
        self._driver = Adafruit_DHT
        self._sensor = Adafruit_DHT.DHT11

    def read(self) -> ClimateReading | None:
        if self._driver is None:
            return None
        humidity, temperature = self._driver.read(self._sensor, self._pin)
        if humidity is None or temperature is None:
            log.warning('El DHT11 no respondio')
            return None
        return ClimateReading(temperature=temperature, humidity=humidity)


class FixedClimateSensor(ClimateSensor):

    def __init__(self, temperature: float, humidity: float):
        self._reading = ClimateReading(temperature=temperature, humidity=humidity)

    def read(self) -> ClimateReading | None:
        return self._reading
