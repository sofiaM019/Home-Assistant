"""
Support for INSTEON dimmers via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging
import asyncio

from homeassistant.components.switch import (SwitchDevice)
from homeassistant.loader import get_component

insteon_plm = get_component('insteon_plm')


DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Moo."""
    _LOGGER.info('Provisioning Insteon PLM Switches')

    plm = hass.data['insteon_plm']

    def async_plm_switch_callback(device):
        """New device detected from transport."""
        name = device['address']
        address = device['address_hex']

        _LOGGER.info('New INSTEON PLM switch device: %s (%s)', name, address)
        hass.async_add_job(
            async_add_devices(
                [InsteonPLMSwitchDevice(hass, plm, address, name)]))

    criteria = dict(capability='switch')
    plm.protocol.devices.add_device_callback(
        async_plm_switch_callback, criteria)

    new_switches = []
    yield from async_add_devices(new_switches)


class InsteonPLMSwitchDevice(SwitchDevice):
    """A Class for an Insteon device."""

    def __init__(self, hass, plm, address, name):
        """Initialize the switch."""
        self._hass = hass
        self._plm = plm.protocol
        self._address = address
        self._name = name

        self._plm.add_update_callback(
            self.async_switch_update, dict(address=self._address))

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
    def is_on(self):
        """Return the boolean response if the node is on."""
        onlevel = self._plm.get_device_attr(self._address, 'onlevel')
        _LOGGER.debug('on level for %s is %s', self._address, onlevel)
        return bool(onlevel)

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        return insteon_plm.common_attributes(self)

    def get_attr(self, key):
        """Return specified attribute for this device."""
        return self._plm.get_device_attr(self.address, key)

    def async_switch_update(self, message):
        """Receive notification from transport that new data exists."""
        _LOGGER.info('Received update calback from PLM for %s', self._address)
        self._hass.async_add_job(self.async_update_ha_state(True))

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Moo."""
        self._plm.turn_on(self._address)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Moo."""
        self._plm.turn_off(self._address)
