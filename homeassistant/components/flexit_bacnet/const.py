"""Constants for the Flexit Nordic (BACnet) integration."""
from flexit_bacnet import VENTILATION_MODE, VENTILATION_MODES

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    PRESET_NONE,
)

DOMAIN = "flexit_bacnet"

CONF_ADDRESS = "address"

CONF_DEVICE_ID = "device_id"

VENTILATION_TO_PRESET_MODE_MAP = {
    VENTILATION_MODES[VENTILATION_MODE.STOP]: PRESET_NONE,
    VENTILATION_MODES[VENTILATION_MODE.AWAY]: PRESET_AWAY,
    VENTILATION_MODES[VENTILATION_MODE.HOME]: PRESET_HOME,
    VENTILATION_MODES[VENTILATION_MODE.HIGH]: PRESET_BOOST,
}

PRESET_TO_VENTILATION_MODE_MAP = {
    PRESET_NONE: VENTILATION_MODE.STOP,
    PRESET_AWAY: VENTILATION_MODE.AWAY,
    PRESET_HOME: VENTILATION_MODE.HOME,
    PRESET_BOOST: VENTILATION_MODE.HIGH,
}
