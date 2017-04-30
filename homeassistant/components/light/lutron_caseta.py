"""
Support for Lutron Caseta lights.


"""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.light.lutron import (
    to_hass_level, to_lutron_level)
from homeassistant.components.lutron_caseta import (
    LUTRON_CASETA_SMARTBRIDGE, LutronCasetaDevice)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lutron_caseta']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Lutron Caseta lights."""
    devs = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    light_devices = bridge.get_devices_by_types(["WallDimmer", "PlugInDimmer"])
    for light_device in light_devices:
        dev = LutronCasetaLight(light_device, bridge)
        devs.append(dev)

    add_devices(devs, True)


class LutronCasetaLight(LutronCasetaDevice, Light):
    """Representation of a Lutron Light, including dimmable."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return to_hass_level(self._state["current_state"])

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            brightness = 255
        self._smartbridge.set_value(self._device_id,
                                    to_lutron_level(brightness))

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._smartbridge.set_value(self._device_id, 0)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state["current_state"] > 0

    def update(self):
        """Call when forcing a refresh of the device."""
        self._state = self._smartbridge.get_device_by_id(self._device_id)
        _LOGGER.debug(self._state)
