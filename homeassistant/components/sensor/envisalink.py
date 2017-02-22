"""
Support for Envisalink sensors (shows panel info).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.envisalink/
"""
import asyncio
import logging

from homeassistant.core import callback
from homeassistant.components.envisalink import (
    DATA_EVL, PARTITION_SCHEMA, CONF_PARTITIONNAME, EnvisalinkDevice,
    EVENT_PARTITION_UPDATE, EVENT_KEYPAD_UPDATE, ATTR_PARTITION)
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['envisalink']
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Perform the setup for Envisalink sensor devices."""
    configured_partitions = discovery_info['partitions']

    devices = []
    for part_num in configured_partitions:
        device_config_data = PARTITION_SCHEMA(configured_partitions[part_num])
        device = EnvisalinkSensor(
            hass,
            device_config_data[CONF_PARTITIONNAME],
            part_num,
            hass.data[DATA_EVL].alarm_state['partition'][part_num],
            hass.data[DATA_EVL])
        devices.append(device)

    yield from async_add_devices(devices)


class EnvisalinkSensor(EnvisalinkDevice, Entity):
    """Representation of an Envisalink keypad."""

    def __init__(self, hass, partition_name, partition_number, info,
                 controller):
        """Initialize the sensor."""
        self._icon = 'mdi:alarm'
        self._partition_number = partition_number

        _LOGGER.debug('Setting up sensor for partition: ' + partition_name)
        super().__init__(partition_name + ' Keypad', info, controller)

        hass.buss.async_listen(EVENT_PARTITION_UPDATE, self._update_callback)
        hass.buss.async_listen(EVENT_KEYPAD_UPDATE, self._update_callback)

    @property
    def icon(self):
        """Return the icon if any."""
        return self._icon

    @property
    def state(self):
        """Return the overall state."""
        return self._info['status']['alpha']

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._info['status']

    @callback
    def _update_callback(self, event):
        """Update the partition state in HA, if needed."""
        partition = event.data[ATTR_PARTITION]

        if partition is None or int(partition) == self._partition_number:
            self.hass.schedule_update_ha_state()
