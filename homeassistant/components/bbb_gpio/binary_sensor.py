"""Support for binary sensor using Beaglebone Black GPIO."""
import logging

import voluptuous as vol

from homeassistant.components import bbb_gpio
from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import CONF_NAME, DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

CONF_PINS = "pins"
CONF_BOUNCETIME = "bouncetime"
CONF_INVERT_LOGIC = "invert_logic"
CONF_PULL_MODE = "pull_mode"

DEFAULT_BOUNCETIME = 50
DEFAULT_INVERT_LOGIC = False
DEFAULT_PULL_MODE = "UP"

PIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_BOUNCETIME, default=DEFAULT_BOUNCETIME): cv.positive_int,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): vol.In(["UP", "DOWN"]),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_PINS, default={}): vol.Schema({cv.string: PIN_SCHEMA})}
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Beaglebone Black GPIO devices."""
    _LOGGER.warning(
        "The BeagleBone Black GPIO integration is deprecated and will be removed "
        "in Home Assistant Core 2022.4; this integration is removed under "
        "Architectural Decision Record 0019, more information can be found here: "
        "https://github.com/home-assistant/architecture/blob/master/adr/0019-GPIO.md"
    )

    pins = config[CONF_PINS]

    binary_sensors = []

    for pin, params in pins.items():
        binary_sensors.append(BBBGPIOBinarySensor(pin, params))
    add_entities(binary_sensors)


class BBBGPIOBinarySensor(BinarySensorEntity):
    """Representation of a binary sensor that uses Beaglebone Black GPIO."""

    _attr_should_poll = False

    def __init__(self, pin, params):
        """Initialize the Beaglebone Black binary sensor."""
        self._pin = pin
        self._attr_name = params[CONF_NAME] or DEVICE_DEFAULT_NAME
        self._bouncetime = params[CONF_BOUNCETIME]
        self._pull_mode = params[CONF_PULL_MODE]
        self._invert_logic = params[CONF_INVERT_LOGIC]

        bbb_gpio.setup_input(self._pin, self._pull_mode)
        self._state = bbb_gpio.read_input(self._pin)

        def read_gpio(pin):
            """Read state from GPIO."""
            self._state = bbb_gpio.read_input(self._pin)
            self.schedule_update_ha_state()

        bbb_gpio.edge_detect(self._pin, read_gpio, self._bouncetime)

    @property
    def is_on(self) -> bool:
        """Return the state of the entity."""
        return self._state != self._invert_logic
