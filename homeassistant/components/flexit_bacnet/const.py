"""Constants for the Flexit Nordic (BACnet) integration."""

from flexit_bacnet import (
    VENTILATION_MODE_AWAY,
    VENTILATION_MODE_HIGH,
    VENTILATION_MODE_HOME,
    VENTILATION_MODE_STOP,
)

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    PRESET_NONE,
)

DOMAIN = "flexit_bacnet"

MAX_TEMP = 30
MIN_TEMP = 10

VENTILATION_TO_PRESET_MODE_MAP = {
    VENTILATION_MODE_STOP: PRESET_NONE,
    VENTILATION_MODE_AWAY: PRESET_AWAY,
    VENTILATION_MODE_HOME: PRESET_HOME,
    VENTILATION_MODE_HIGH: PRESET_BOOST,
}

PRESET_TO_VENTILATION_MODE_MAP = {
    PRESET_NONE: VENTILATION_MODE_STOP,
    PRESET_AWAY: VENTILATION_MODE_AWAY,
    PRESET_HOME: VENTILATION_MODE_HOME,
    PRESET_BOOST: VENTILATION_MODE_HIGH,
}
