"""
Support for setting the Transmission BitTorrent client Turtle Mode.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.transmission/
"""
from datetime import timedelta

import logging

from homeassistant.components.transmission import (
    DATA_TRANSMISSION, DOMAIN)
from homeassistant.const import (
    STATE_OFF, STATE_ON)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import Throttle

DEPENDENCIES = ['transmission']

_LOGGING = logging.getLogger(__name__)

DEFAULT_NAME = 'Transmission Turtle Mode'
DATA_UPDATED = '{}_data_updated'.format(DOMAIN)
 
async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Transmission switch."""
    if discovery_info is None:
        return

    component_name = DATA_TRANSMISSION
    transmission_api = hass.data[component_name]
    name = discovery_info['client_name']

    add_entities([TransmissionSwitch(transmission_api, name)], True)


class TransmissionSwitch(RestoreEntity):
    """Representation of a Transmission switch."""

    def __init__(self, transmission_client, name):
        """Initialize the Transmission switch."""
        self._name = name
        self.transmission_client = transmission_client
        self._state = STATE_OFF

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def should_poll(self):
        """Poll for status regularly."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """Turn the device on."""
        _LOGGING.debug("Turning Turtle Mode of Transmission on")
        self.transmission_client.set_alt_speed_enabled(True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGING.debug("Turning Turtle Mode of Transmission off")
        self.transmission_client.set_alt_speed_enabled(False)

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            return
        self._state = state.state

        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    def update(self):
        """Get the latest data from Transmission and updates the state."""
        active = self.transmission_client.get_alt_speed_enabled()

        if active is None:
            return

        self._state = STATE_ON if active else STATE_OFF
