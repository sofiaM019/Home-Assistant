"""
Support for FutureNow Ethernet unit outputs as Lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.futurenow/
"""

import logging
import time
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, CONF_DEVICES)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light,
    PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyfnip']

_LOGGER = logging.getLogger(__name__)

CONF_DRIVER = 'driver'
CONF_DRIVER_FNIP6X10AD = 'FNIP6x10ad'
CONF_DRIVER_FNIP8X10A = 'FNIP8x10a'
CONF_DRIVER_TYPES = [CONF_DRIVER_FNIP6X10AD, CONF_DRIVER_FNIP8X10A]

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional('dimmable'): int,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DRIVER): vol.In(CONF_DRIVER_TYPES),
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.string,
    vol.Required(CONF_DEVICES): {cv.string: DEVICE_SCHEMA},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    import pyfnip

    lights = []
    for channel, device_config in config[CONF_DEVICES].items():
        device = {}
        device['name'] = device_config[CONF_NAME]
        device['dimmable'] = True if 'dimmable' in device_config else False
        device['channel'] = channel
        device['driver'] = config[CONF_DRIVER]
        device['host'] = config[CONF_HOST]
        device['port'] = config[CONF_PORT]
        lights.append(FutureNowLight(device))

    add_devices(lights)


def to_futurenow_level(level):
    """Convert the given HASS light level (0-255) to FutureNow (0-100)."""
    return int((level * 100) / 255)


def to_hass_level(level):
    """Convert the given FutureNow (0-100) light level to HASS (0-255)."""
    return int((level * 255) / 100)


class FutureNowLight(Light):
    """Representation of an FutureNow light."""

    def __init__(self, device):
        """Initialize the light."""
        import pyfnip

        self._name = device['name']
        self._dimmable = device['dimmable']
        self._channel = device['channel']
        self._brightness = None
        self._state = None

        if device['driver'] == CONF_DRIVER_FNIP6X10AD:
            self._light = pyfnip.FNIP6x2adOutput(device['host'], 
                                                 device['port'], self._channel)
        if device['driver'] == CONF_DRIVER_FNIP8X10A:
            self._light = pyfnip.FNIP8x10aOutput(device['host'], 
                                                 device['port'], self._channel)

        """Get actual state of light."""
        self.update()

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
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._dimmable is True:
            return SUPPORT_BRIGHTNESS
        return 0

    def turn_on(self, **kwargs):
        """Turn the light on."""
        level = kwargs.get(ATTR_BRIGHTNESS, 255) if self._dimmable else 255
        self._light.turn_on(to_futurenow_level(level))

    def turn_off(self, **kwargs):
        self._light.turn_off()

    def update(self):
        """Fetch new state data for this light."""
        """Delay a bit until state change has fully finished."""
        time.sleep(.500)

        state = int(self._light.is_on())
        if state > 0:
            self._state = True
            self._brightness = to_hass_level(state)
        else:
            if self._dimmable:
                self._brightness = 0
            self._state = False
