"""
Support for Ambient Weather Station binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.ambient_station/
"""
import logging

from homeassistant.components.ambient_station import (
    SENSOR_TYPES, AmbientWeatherEntity)
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import ATTR_NAME

from .const import ATTR_LAST_DATA, DATA_CLIENT, DOMAIN, TYPE_BINARY_SENSOR

DEPENDENCIES = ['ambient_station']
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up Ambient PWS binary sensors based on the old way."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Ambient PWS binary sensors based on a config entry."""
    ambient = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    binary_sensor_list = []
    for mac_address, station in ambient.stations.items():
        for condition in ambient.monitored_conditions:
            name, _, kind, device_class = SENSOR_TYPES[condition]
            if kind == TYPE_BINARY_SENSOR:
                binary_sensor_list.append(
                    AmbientWeatherBinarySensor(
                        ambient, mac_address, station[ATTR_NAME], condition,
                        name, device_class))

    async_add_entities(binary_sensor_list, True)


class AmbientWeatherBinarySensor(AmbientWeatherEntity, BinarySensorDevice):
    """Define an Ambient binary sensor."""

    def __init__(
            self, ambient, mac_address, station_name, sensor_type, sensor_name,
            device_class):
        """Initialize the sensor."""
        super().__init__(
            ambient, mac_address, station_name, sensor_type, sensor_name)

        self._device_class = device_class

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    async def async_update(self):
        """Fetch new state data for the entity."""
        self._state = self._ambient.stations[
            self._mac_address][ATTR_LAST_DATA].get(self._sensor_type)
