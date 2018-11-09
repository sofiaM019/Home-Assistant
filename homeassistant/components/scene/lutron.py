"""
Support for Lutron scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.lutron/
"""
import logging

from homeassistant.components.lutron import (
    LutronDevice, LUTRON_DEVICES, LUTRON_CONTROLLER)
from homeassistant.components.scene import Scene
from homeassistant.const import (STATE_ON, STATE_OFF)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lutron']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Lutron lights."""
    devs = []
    for scene_data in hass.data[LUTRON_DEVICES]['scene']:
        (area_name, keypad_name, device, led) = scene_data
        dev = LutronScene(area_name, keypad_name, device, led,
                          hass.data[LUTRON_CONTROLLER])
        devs.append(dev)

    add_entities(devs, True)
    return True


class LutronScene(LutronDevice, Scene):
    """Representation of a Lutron Switch."""

    def __init__(self,
                 area_name,
                 keypad_name,
                 lutron_device,
                 lutron_led,
                 controller):
        """Initialize the scene/button."""
        LutronDevice.__init__(self, area_name, lutron_device, controller)
        self._keypad_name = keypad_name
        self._led = lutron_led

    def activate(self):
        """Activate the scene."""
        self._lutron_device.press()

    @property
    def state(self):
        """Return the state of the scene."""
        return STATE_ON if self._led.state else STATE_OFF

    @property
    def name(self):
        """Return the name of the device."""
        return "{} {}: {}".format(self._area_name,
                                  self._keypad_name,
                                  self._lutron_device.name)
