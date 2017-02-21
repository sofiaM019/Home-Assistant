"""
Support for Wink switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.wink/
"""

from homeassistant.components.wink import WinkDevice, DOMAIN
from homeassistant.helpers.entity import ToggleEntity

DEPENDENCIES = ['wink']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink platform."""
    import pywink

    for switch in pywink.get_switches():
        _id = switch.object_id() + switch.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkToggleDevice(switch, hass)])
    for switch in pywink.get_powerstrips():
        _id = switch.object_id() + switch.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkToggleDevice(switch, hass)])
    for switch in pywink.get_sirens():
        _id = switch.object_id() + switch.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkToggleDevice(switch, hass)])
    for sprinkler in pywink.get_sprinklers():
        _id = sprinkler.object_id() + sprinkler.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkToggleDevice(sprinkler, hass)])
    for scene in pywink.get_scenes():
        _id = scene.object_id() + scene.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkScene(scene, hass)])


class WinkToggleDevice(WinkDevice, ToggleEntity):
    """Representation of a Wink toggle device."""

    def __init__(self, wink, hass):
        """Initialize the Wink device."""
        super().__init__(wink, hass)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.wink.state()

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.wink.set_state(True)

    def turn_off(self):
        """Turn the device off."""
        self.wink.set_state(False)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        try:
            event = self.wink.last_event()
        except AttributeError:
            event = None
        return {
            'last_event': event
        }


class WinkScene(WinkDevice, ToggleEntity):
    """Representation of a Wink shorcut/scene."""

    def __init__(self, wink, hass):
        """Initialize the Wink device."""
        super().__init__(wink, hass)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.wink.state()

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.wink.activate()

    def turn_off(self):
        """Scene can only be turned on."""
        return
