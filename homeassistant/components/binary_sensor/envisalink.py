"""
Support for Envisalink zone states- represented as binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.envisalink/
"""
import asyncio
import logging

from homeassistant.core import callback
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.envisalink import (
    DATA_EVL, ZONE_SCHEMA, CONF_ZONENAME, CONF_ZONETYPE, EnvisalinkDevice,
    DATA_EVL_BINARY)
from homeassistant.const import ATTR_LAST_TRIP_TIME

DEPENDENCIES = ['envisalink']
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup Envisalink binary sensor devices."""
    configured_zones = discovery_info['zones']

    devices = []
    for zone_num in configured_zones:
        device_config_data = ZONE_SCHEMA(configured_zones[zone_num])
        device = EnvisalinkBinarySensor(
            hass,
            zone_num,
            device_config_data[CONF_ZONENAME],
            device_config_data[CONF_ZONETYPE],
            hass.data[DATA_EVL].alarm_state['zone'][zone_num],
            hass.data[DATA_EVL]
        )
        devices.append(device)

    hass.data[DATA_EVL_BINARY] = devices
    yield from async_add_devices(devices)


class EnvisalinkBinarySensor(EnvisalinkDevice, BinarySensorDevice):
    """Representation of an Envisalink binary sensor."""

    def __init__(self, hass, zone_number, zone_name, zone_type, info,
                 controller):
        """Initialize the binary_sensor."""
        self._zone_type = zone_type
        self._zone_number = zone_number

        _LOGGER.debug('Setting up zone: ' + zone_name)
        super().__init__(zone_name, info, controller)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr[ATTR_LAST_TRIP_TIME] = self._info['last_fault']
        return attr

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._info['status']['open']

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._zone_type

    @callback
    def update_callback(self, zone):
        """Update the zone's state, if needed."""
        if zone is None or int(zone) == self._zone_number:
            self.hass.async_add_job(self.async_update_ha_state())
