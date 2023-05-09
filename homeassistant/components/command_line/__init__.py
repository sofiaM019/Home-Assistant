"""The command_line component."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
    STATE_CLASSES_SCHEMA as SENSOR_STATE_CLASSES_SCHEMA,
)
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_COMMAND,
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STATE,
    CONF_COMMAND_STOP,
    CONF_COVERS,
    CONF_DEVICE_CLASS,
    CONF_FRIENDLY_NAME,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN

BINARY_SENSOR_DEFAULT_NAME = "Binary Command Sensor"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
CONF_JSON_ATTRIBUTES = "json_attributes"
SENSOR_DEFAULT_NAME = "Command Sensor"
CONF_NOTIFIERS = "notifiers"

PLATFORM_MAPPING = {
    CONF_BINARY_SENSORS: Platform.BINARY_SENSOR,
    CONF_COVERS: Platform.COVER,
    CONF_NOTIFIERS: Platform.NOTIFY,
    CONF_SENSORS: Platform.SENSOR,
    CONF_SWITCHES: Platform.SWITCH,
}

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND): cv.string,
        vol.Optional(CONF_NAME, default=BINARY_SENSOR_DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)
COVER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COMMAND_CLOSE, default="true"): cv.string,
        vol.Optional(CONF_COMMAND_OPEN, default="true"): cv.string,
        vol.Optional(CONF_COMMAND_STATE): cv.string,
        vol.Optional(CONF_COMMAND_STOP, default="true"): cv.string,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)
NOTIFY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)
SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND): cv.string,
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_JSON_ATTRIBUTES): cv.ensure_list_csv,
        vol.Optional(CONF_NAME, default=SENSOR_DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLASS): SENSOR_STATE_CLASSES_SCHEMA,
    }
)
SWITCH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COMMAND_OFF, default="true"): cv.string,
        vol.Optional(CONF_COMMAND_ON, default="true"): cv.string,
        vol.Optional(CONF_COMMAND_STATE): cv.string,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)
COMBINED_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_BINARY_SENSORS): cv.schema_with_slug_keys(
            BINARY_SENSOR_SCHEMA
        ),
        vol.Optional(CONF_COVERS): cv.schema_with_slug_keys(COVER_SCHEMA),
        vol.Optional(CONF_NOTIFIERS): cv.schema_with_slug_keys(NOTIFY_SCHEMA),
        vol.Optional(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
        vol.Optional(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA),
    }
)
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.All(
            COMBINED_SCHEMA,
            cv.has_at_least_one_key(
                CONF_BINARY_SENSORS,
                CONF_COVERS,
                CONF_NOTIFIERS,
                CONF_SENSORS,
                CONF_SWITCHES,
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Command Line from yaml config."""
    command_line_config: dict[str, dict[str, Any]] = config.get(DOMAIN, {})
    if not command_line_config:
        return True

    _LOGGER.debug("Full config loaded: %s", command_line_config)

    load_coroutines: list[Coroutine[Any, Any, None]] = []
    platforms: list[Platform] = []
    for platform, configs in command_line_config.items():
        platforms.append(PLATFORM_MAPPING[platform])
        for object_id, object_config in configs.items():
            platform_config = {"object_id": object_id, "config": object_config}
            if PLATFORM_MAPPING[platform] == Platform.NOTIFY and (
                add_name := object_config.get(CONF_NAME)
            ):
                platform_config[CONF_NAME] = add_name
            _LOGGER.debug(
                "Loading config %s for platform %s",
                platform_config,
                PLATFORM_MAPPING[platform],
            )
            load_coroutines.append(
                discovery.async_load_platform(
                    hass,
                    PLATFORM_MAPPING[platform],
                    DOMAIN,
                    platform_config,
                    config,
                )
            )

    await async_setup_reload_service(hass, DOMAIN, platforms)

    if load_coroutines:
        _LOGGER.debug("Loading platforms: %s", platforms)
        await asyncio.gather(*load_coroutines)

    return True
