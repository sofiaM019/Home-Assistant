"""Allows to configure a switch using RPi GPIO."""
import logging

from homeassistant.components import remote_rpi_gpio
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import DEVICE_DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['remote_rpi_gpio']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Remote Raspberry PI GPIO devices."""
    if discovery_info is None:
        return

    address = discovery_info['address']
    invert_logic = discovery_info['invert_logic']
    ports = discovery_info['switches']

    devices = []
    for port, name in ports.items():
        try:
            led = remote_rpi_gpio.setup_output(address,
                                               port,
                                               invert_logic)
        except (ValueError, IndexError, KeyError, IOError):
            return None
        new_switch = RemoteRPiGPIOSwitch(name, led, invert_logic)
        devices.append(new_switch)
    add_entities(devices)


class RemoteRPiGPIOSwitch(SwitchDevice):
    """Representation of a Remtoe Raspberry Pi GPIO."""

    def __init__(self, name, led, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = False
        self._invert_logic = invert_logic
        self._switch = led

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        remote_rpi_gpio.write_output(self._switch,
                                     0 if self._invert_logic else 1)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        remote_rpi_gpio.write_output(self._switch,
                                     1 if self._invert_logic else 0)
        self._state = False
        self.schedule_update_ha_state()
