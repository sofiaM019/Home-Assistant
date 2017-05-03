"""
Support for Verisure Smartplugs.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.verisure/
"""
import logging
from time import sleep

from homeassistant.components.verisure import HUB as hub
from homeassistant.components.verisure import CONF_SMARTPLUGS
from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Verisure switch platform."""
    if not int(hub.config.get(CONF_SMARTPLUGS, 1)):
        return False

    hub.update_overview()
    switches = []
    switches.extend([
        VerisureSmartplug(device_label)
        for device_label in hub.get(
            hub.overview,
            '$.smartPlugs[*].deviceLabel')])
    add_devices(switches)


class VerisureSmartplug(SwitchDevice):
    """Representation of a Verisure smartplug."""

    def __init__(self, device_id):
        """Initialize the Verisure device."""
        self._device_label = device_id

    @property
    def name(self):
        """Return the name or location of the smartplug."""
        res = hub.get(
            "$.smartPlugs[?(@.deviceLabel == '%s')].area",
            self._device_label)
        return res[0] if res else 'UNKNOWN'

    @property
    def is_on(self):
        """Return true if on."""
        res = hub.get(
            "$.smartPlugs[?(@.deviceLabel == '%s')].currentState",
            self._device_label)
        return res[0] == 'ON' if res else 'UNKNOWN'

    @property
    def available(self):
        """Return True if entity is available."""
        res = hub.get(
            "$.smartPlugs[?(@.deviceLabel == '%s')]",
            self._device_label)
        return True if res else False

    def turn_on(self):
        """Set smartplug status on."""
        hub.session.set_smartplug_state(self._device_label, True)
        for _ in range(10):
            sleep(1)
            hub.update_overview(no_throttle=True)
            if self.is_on:
                return

    def turn_off(self):
        """Set smartplug status off."""
        hub.session.set_smartplug_state(self._device_label, False)
        for _ in range(10):
            sleep(1)
            hub.update_overview(no_throttle=True)
            if not self.is_on:
                return

    def update(self):
        """Get the latest date of the smartplug."""
        hub.update_overview()
