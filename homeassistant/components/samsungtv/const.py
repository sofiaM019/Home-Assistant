"""Constants for the Samsung TV integration."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "samsungtv"

DEFAULT_NAME = "Samsung TV Remote"

CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"

METHODS = ("websocket", "legacy")
