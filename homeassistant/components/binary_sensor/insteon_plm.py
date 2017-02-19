"""
Support for INSTEON dimmers via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging
import asyncio

from homeassistant.components.binary_sensor import (BinarySensorDevice)
from homeassistant.loader import get_component

insteon_plm = get_component('insteon_plm')

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Moo."""
    _LOGGER.info('Provisioning Insteon PLM Binary Sensors')

    plm = hass.data['insteon_plm']

    def async_plm_binarysensor_callback(device):
        """New device detected from transport."""
        name = device['address']
        address = device['address_hex']

        _LOGGER.info('New INSTEON PLM binary sensor device: %s (%s)',
                     name, address)
        hass.async_add_job(async_add_devices(
            [InsteonPLMBinarySensorDevice(hass, plm, address, name)]))

    criteria = dict(capability='binary_sensor')
    plm.protocol.devices.add_device_callback(
        async_plm_binarysensor_callback, criteria)

    new_binarysensors = []
    yield from async_add_devices(new_binarysensors)


class InsteonPLMBinarySensorDevice(BinarySensorDevice):
    """A Class for an Insteon device."""

    def __init__(self, hass, plm, address, name):
        """Initialize the binarysensor."""
        self._hass = hass
        self._plm = plm.protocol
        self._address = address
        self._name = name

        self._plm.add_update_callback(
            self.async_binarysensor_update, dict(address=self._address))

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def address(self):
        """Return the the address of the node."""
        return self._address

    @property
    def name(self):
        """Return the the name of the node."""
        return self._name

    @property
    def sensor_class(self):
        """Sensor class is unknown."""
        return

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        sensorstate = self._plm.get_device_attr(self._address, 'sensorstate')
        _LOGGER.info('sensor state for %s is %s', self._address, sensorstate)
        return bool(sensorstate)

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        return insteon_plm.common_attributes(self)

    def get_attr(self, key):
        """Return specified attribute for this device."""
        return self._plm.get_device_attr(self.address, key)

    def async_binarysensor_update(self, message):
        """Receive notification from transport that new data exists."""
        _LOGGER.info('Received update calback from PLM for %s', self._address)
        self._hass.async_add_job(self.async_update_ha_state(True))
