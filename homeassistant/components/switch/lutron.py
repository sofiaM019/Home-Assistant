"""
Support for Lutron switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.lutron/
"""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.components.lutron import (
    LutronDevice, LUTRON_DEVICES, LUTRON_CONTROLLER)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lutron']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Lutron switches."""
    devs = []
    for (area_name, device) in hass.data[LUTRON_DEVICES]['switch']:
        dev = LutronSwitch(area_name, device, hass.data[LUTRON_CONTROLLER])
        devs.append(dev)

    add_entities(devs, True)
    return True


class LutronSwitch(LutronDevice, SwitchDevice):
    """Representation of a Lutron Switch."""

    def __init__(self, area_name, lutron_device, controller):
        """Initialize the switch."""
        LutronDevice.__init__(self, area_name, lutron_device, controller)

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._lutron_device.level = 100

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._lutron_device.level = 0

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr['Lutron Integration ID'] = self._lutron_device.id
        return attr

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._lutron_device.last_level() > 0
