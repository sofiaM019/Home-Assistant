"""Support for tracking the moon phases."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Moon"

STATE_NEW_MOON = "new_moon"
STATE_WAXING_CRESCENT = "waxing_crescent"
STATE_FIRST_QUARTER = "first_quarter"
STATE_WAXING_GIBBOUS = "waxing_gibbous"
STATE_FULL_MOON = "full_moon"
STATE_WANING_GIBBOUS = "waning_gibbous"
STATE_LAST_QUARTER = "last_quarter"
STATE_WANING_CRESCENT = "waning_crescent"

MOON_ICONS = {
    STATE_NEW_MOON: "mdi:moon-new",
    STATE_WAXING_CRESCENT: "mdi:moon-waxing-crescent",
    STATE_FIRST_QUARTER: "mdi:moon-first-quarter",
    STATE_WAXING_GIBBOUS: "mdi:moon-waxing-gibbous",
    STATE_FULL_MOON: "mdi:moon-full",
    STATE_WANING_GIBBOUS: "moon-waning-gibbous",
    STATE_LAST_QUARTER: "mdi:moon-last-quarter",
    STATE_WANING_CRESCENT: "mdi:moon-waning-crescent"
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Moon sensor."""
    name = config.get(CONF_NAME)

    async_add_entities([MoonSensor(name)], True)


class MoonSensor(Entity):
    """Representation of a Moon sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._state == 0:
            return "new_moon"
        if self._state < 7:
            return "waxing_crescent"
        if self._state == 7:
            return "first_quarter"
        if self._state < 14:
            return "waxing_gibbous"
        if self._state == 14:
            return "full_moon"
        if self._state < 21:
            return "waning_gibbous"
        if self._state == 21:
            return "last_quarter"
        return "waning_crescent"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return MOON_ICONS.get(self._state, "mdi:brightness-3")

    async def async_update(self):
        """Get the time and updates the states."""
        from astral import Astral

        today = dt_util.as_local(dt_util.utcnow()).date()
        self._state = Astral().moon_phase(today)
