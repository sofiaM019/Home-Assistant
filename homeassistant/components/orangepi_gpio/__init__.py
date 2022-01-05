"""Support for controlling GPIO pins of a Orange Pi."""
import logging

from OPi import GPIO

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import PIN_MODES

_LOGGER = logging.getLogger(__name__)

DOMAIN = "orangepi_gpio"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Orange Pi GPIO component."""
    _LOGGER.warning(
        "The Orange Pi GPIO integration is deprecated and will be removed "
        "in Home Assistant Core 2022.4; this integration is removed under "
        "Architectural Decision Record 0019, more information can be found here: "
        "https://github.com/home-assistant/architecture/blob/master/adr/0019-GPIO.md"
    )

    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        GPIO.cleanup()

    def prepare_gpio(event):
        """Stuff to do when Home Assistant starts."""
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)
    return True


def setup_mode(mode):
    """Set GPIO pin mode."""
    _LOGGER.debug("Setting GPIO pin mode as %s", PIN_MODES[mode])
    GPIO.setmode(PIN_MODES[mode])


def setup_input(port):
    """Set up a GPIO as input."""
    _LOGGER.debug("Setting up GPIO pin %i as input", port)
    GPIO.setup(port, GPIO.IN)


def read_input(port):
    """Read a value from a GPIO."""
    _LOGGER.debug("Reading GPIO pin %i", port)
    return GPIO.input(port)


def edge_detect(port, event_callback):
    """Add detection for RISING and FALLING events."""
    _LOGGER.debug("Add callback for GPIO pin %i", port)
    GPIO.add_event_detect(port, GPIO.BOTH, callback=event_callback)
