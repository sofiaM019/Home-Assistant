"""
Asuswrt status sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.asuswrt/
"""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.components.asuswrt import DATA_ASUSWRT

DEPENDENCIES = ['asuswrt']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, add_entities, discovery_info=None):
    """Set up the asuswrt sensors."""
    api = hass.data[DATA_ASUSWRT]
    add_entities([
        AsuswrtRXSensor(api),
        AsuswrtTXSensor(api),
        AsuswrtTotalRXSensor(api),
        AsuswrtTotalTXSensor(api)
    ])


class AsuswrtSensor(Entity):
    """Representation of a asuswrt sensor."""

    _name = 'generic'

    def __init__(self, api):
        """Initialize the sensor."""
        self._api = api
        self._state = None
        self._rates = None
        self._speed = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Fetch status from asuswrt."""
        self._rates = await self._api.async_get_packets_total()
        self._speed = await self._api.async_get_current_transfer_rates()


class AsuswrtRXSensor(AsuswrtSensor):
    """Representation of a asuswrt download speed sensor."""

    _name = 'Asuswrt Download Speed'
    _unit = 'Mbit/s'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_device_update()
        if self._speed is not None:
            self._state = round(self._speed[0] / 125000, 2)


class AsuswrtTXSensor(AsuswrtSensor):
    """Representation of a asuswrt upload speed sensor."""

    _name = 'Asuswrt Upload Speed'
    _unit = 'Mbit/s'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_device_update()
        if self._speed is not None:
            self._state = round(self._speed[1] / 125000, 2)


class AsuswrtTotalRXSensor(AsuswrtSensor):
    """Representation of a asuswrt total download sensor."""

    _name = 'Asuswrt Total Download'
    _unit = 'Gigabyte'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_device_update()
        if self._rates is not None:
            self._state = round(self._rates[0] / 1000000000, 1)


class AsuswrtTotalTXSensor(AsuswrtSensor):
    """Representation of a asuswrt total upload sensor."""

    _name = 'Asuswrt Total Upload'
    _unit = 'Gigabyte'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_device_update()
        if self._rates is not None:
            self._state = round(self._rates[1] / 1000000000, 1)
