"""Collection of useful functions for the HomeKit component."""
import logging

import voluptuous as vol

from homeassistant.core import split_entity_id
from homeassistant.components.fan import (
    SPEED_HIGH, SPEED_LOW, SPEED_MEDIUM, SPEED_OFF)
from homeassistant.const import (
    ATTR_CODE, CONF_NAME, TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.temperature as temp_util
from .const import HOMEKIT_NOTIFY_ID

_LOGGER = logging.getLogger(__name__)


def validate_entity_config(values):
    """Validate config entry for CONF_ENTITY."""
    entities = {}
    for entity_id, config in values.items():
        entity = cv.entity_id(entity_id)
        params = {}
        if not isinstance(config, dict):
            raise vol.Invalid('The configuration for "{}" must be '
                              ' a dictionary.'.format(entity))

        for key in (CONF_NAME, ):
            value = config.get(key, -1)
            if value != -1:
                params[key] = cv.string(value)

        domain, _ = split_entity_id(entity)

        if domain == 'alarm_control_panel':
            code = config.get(ATTR_CODE)
            params[ATTR_CODE] = cv.string(code) if code else None

        entities[entity] = params
    return entities


def show_setup_message(hass, bridge):
    """Display persistent notification with setup information."""
    pin = bridge.pincode.decode()
    _LOGGER.info('Pincode: %s', pin)
    message = 'To setup Home Assistant in the Home App, enter the ' \
              'following code:\n### {}'.format(pin)
    hass.components.persistent_notification.create(
        message, 'HomeKit Setup', HOMEKIT_NOTIFY_ID)


def dismiss_setup_message(hass):
    """Dismiss persistent notification and remove QR code."""
    hass.components.persistent_notification.dismiss(HOMEKIT_NOTIFY_ID)


def convert_to_float(state):
    """Return float of state, catch errors."""
    try:
        return float(state)
    except (ValueError, TypeError):
        return None


def temperature_to_homekit(temperature, unit):
    """Convert temperature to Celsius for HomeKit."""
    return round(temp_util.convert(temperature, unit, TEMP_CELSIUS), 1)


def temperature_to_states(temperature, unit):
    """Convert temperature back from Celsius to Home Assistant unit."""
    return round(temp_util.convert(temperature, TEMP_CELSIUS, unit), 1)


def density_to_air_quality(density):
    """Map PM2.5 density to HomeKit AirQuality level."""
    if density <= 35:
        return 1
    elif density <= 75:
        return 2
    elif density <= 115:
        return 3
    elif density <= 150:
        return 4
    return 5


def fan_value_to_speed(value):
    """Convert HomeKit value to fan speed setting."""
    if value == 0:
        return SPEED_OFF
    elif value <= 33:
        return SPEED_LOW
    elif value <= 66:
        return SPEED_MEDIUM
    return SPEED_HIGH


def fan_speed_to_value(speed):
    """Convert fan speed setting to HomeKit value."""
    if speed == SPEED_OFF:
        return 0
    elif speed == SPEED_LOW:
        return 33
    elif speed == SPEED_MEDIUM:
        return 66
    elif speed == SPEED_HIGH:
        return 100
    return None
