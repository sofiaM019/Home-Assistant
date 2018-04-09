"""
Support for Eufy lights

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.eufy/
"""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP, SUPPORT_COLOR, Light)

import homeassistant.util.color as color_util

from homeassistant.util.color import (
    color_temperature_mired_to_kelvin as mired_to_kelvin,
    color_temperature_kelvin_to_mired as kelvin_to_mired)

DEPENDENCIES = ['eufy']

_LOGGER = logging.getLogger(__name__)

EUFY_MAX_KELVIN = 6500
EUFY_MIN_KELVIN = 2700


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Eufy bulbs."""
    if discovery_info is None:
        return
    add_devices([EufyLight(discovery_info)], True)


class EufyLight(Light):
    """Representation of a Eufy light."""

    def __init__(self, device):
        """Initialize the light."""
        # pylint: disable=import-error
        import lakeside

        self._name = device['name']
        self._address = device['address']
        self._code = device['code']
        self._type = device['type']
        self._bulb = lakeside.bulb(self._address, self._code, self._type)
        if self._type == "T1011":
            self._features = SUPPORT_BRIGHTNESS
        elif self._type == "T1012":
            self._features = SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP
        elif self._type == "T1013":
            self._features = SUPPORT_BRIGHTNESS | SUPPORT_COLOR
        self._bulb.connect()

    def update(self):
        self._bulb.update()
        self._brightness = self._bulb.brightness
        self._temp = self._bulb.temperature
        if self._bulb.colors:
            self._hs = color_util.color_RGB_to_hsv(self._bulb.colors)
        else:
            self._hs = None
        self._state = self._bulb.power

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._address

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int(self._brightness * 255 / 100)

    @property
    def min_mireds(self):
        """Return minimum supported color temperature."""
        return kelvin_to_mired(EUFY_MAX_KELVIN)

    @property
    def max_mireds(self):
        """Return maximu supported color temperature."""
        return kelvin_to_mired(EUFY_MIN_KELVIN)

    @property
    def color_temp(self):
        """Return the color temperature of this light."""
        temp_in_k = int(EUFY_MIN_KELVIN + (self._temp *
                                           (EUFY_MAX_KELVIN - EUFY_MIN_KELVIN)
                                           / 100))
        return kelvin_to_mired(temp_in_k)

    @property
    def hs_color(self):
        """Return the color of this light."""
        return self._hs

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    def turn_on(self, **kwargs):
        """Turn the specified light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        colortemp = kwargs.get(ATTR_COLOR_TEMP)
        hs = kwargs.get(ATTR_HS_COLOR)

        if brightness is not None:
            brightness = int(brightness * 100 / 255)
        else:
            brightness = max(1, self._brightness)

        if colortemp is not None:
            temp_in_k = mired_to_kelvin(colortemp)
            relative_temp = temp_in_k - EUFY_MIN_KELVIN
            temp = int(relative_temp * 100 /
                       (EUFY_MAX_KELVIN - EUFY_MIN_KELVIN))
        else:
            temp = None

        if hs is not None:
            rgb = color_util.color_hsv_to_RGB(
                hs[0], hs[1], brightness / 255 * 100)
        else:
            rgb = None

        try:
            self._bulb.set_state(power=True, brightness=brightness,
                                 temperature=temp, colors=rgb)
        except BrokenPipeError:
            self._bulb.connect()
            self._bulb.set_state(power=True, brightness=brightness,
                                 temperature=temp, colors=rgb)

    def turn_off(self, **kwargs):
        """Turn the specified light off."""
        try:
            self._bulb.set_state(power=False)
        except BrokenPipeError:
            self._bulb.connect()
            self._bulb.set_state(power=False)
