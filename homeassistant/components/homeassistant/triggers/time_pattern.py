"""Offer time listening automation rules."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change

# mypy: allow-untyped-defs, no-check-untyped-defs

CONF_HOURS = "hours"
CONF_MINUTES = "minutes"
CONF_SECONDS = "seconds"

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_PLATFORM): "time_pattern",
            CONF_HOURS: cv.TimePattern(maximum=cv.TIME_PATTERN_HOURS_MAX),
            CONF_MINUTES: cv.TimePattern(maximum=cv.TIME_PATTERN_MINUTES_MAX),
            CONF_SECONDS: cv.TimePattern(maximum=cv.TIME_PATTERN_SECONDS_MAX),
        }
    ),
    cv.has_at_least_one_key(CONF_HOURS, CONF_MINUTES, CONF_SECONDS),
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    hours = config.get(CONF_HOURS)
    minutes = config.get(CONF_MINUTES)
    seconds = config.get(CONF_SECONDS)

    # If larger units are specified, default the smaller units to zero
    if minutes is None and hours is not None:
        minutes = 0
    if seconds is None and minutes is not None:
        seconds = 0

    @callback
    def time_automation_listener(now):
        """Listen for time changes and calls action."""
        hass.async_run_job(
            action,
            {
                "trigger": {
                    "platform": "time_pattern",
                    "now": now,
                    "description": "time pattern",
                }
            },
        )

    return async_track_time_change(
        hass, time_automation_listener, hour=hours, minute=minutes, second=seconds
    )
