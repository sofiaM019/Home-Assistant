"""
Support for Vera switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.vera/
"""
import logging

from homeassistant.components.hdmi_cec import CecDevice, CEC_DEVICES, CEC_CLIENT
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['hdmi_cec']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Vera switches."""
    _LOGGER.debug("setting CEC switches")
    add_devices(
        CecSwitch(CEC_CLIENT, logical=device) for
        device in CEC_DEVICES['switch'])


class CecSwitch(CecDevice, SwitchDevice):
    """Representation of a Vera Switch."""

    def __init__(self, cecClient, logical=None, physical=None):
        """Initialize the Vera device."""
        self._state = False
        CecDevice.__init__(self, cecClient, logical, physical)
