"""
Support for ISY994 switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.isy994/
"""
import logging
from typing import Callable  # noqa

from homeassistant.components.switch import SwitchDevice, DOMAIN
from homeassistant.components.isy994 import (ISY994_NODES, ISY994_PROGRAMS,
                                             KEY_ACTIONS, KEY_STATUS,
                                             ISYDevice)
from homeassistant.helpers.typing import ConfigType  # noqa

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config: ConfigType,
                   add_devices: Callable[[list], None], discovery_info=None):
    """Set up the ISY994 switch platform."""
    devices = []
    for node in hass.data[ISY994_NODES][DOMAIN]:
        if not node.dimmable:
            devices.append(ISYSwitchDevice(node))

    for program in hass.data[ISY994_PROGRAMS].get(DOMAIN, []):
        try:
            status = program[KEY_STATUS]
            actions = program[KEY_ACTIONS]
            assert actions.dtype == 'program', 'Not a program'
        except (AttributeError, KeyError, AssertionError):
            _LOGGER.warning("Program '%s' failed to load due to "
                            "incompatible folder structure.", program.name)
        else:
            devices.append(ISYSwitchProgram(program.name, status, actions))

    add_devices(devices)


class ISYSwitchDevice(ISYDevice, SwitchDevice):
    """Representation of an ISY994 switch device."""

    def __init__(self, node) -> None:
        """Initialize the ISY994 switch device."""
        ISYDevice.__init__(self, node)

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 device is in the on state."""
        return bool(self.value)

    def turn_off(self, **kwargs) -> None:
        """Send the turn on command to the ISY994 switch."""
        if not self._node.off():
            _LOGGER.debug('Unable to turn on switch.')

    def turn_on(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch."""
        if not self._node.on():
            _LOGGER.debug('Unable to turn on switch.')


class ISYSwitchProgram(ISYSwitchDevice):
    """A representation of an ISY994 program switch."""

    def __init__(self, name: str, node, actions) -> None:
        """Initialize the ISY994 switch program."""
        ISYSwitchDevice.__init__(self, node)
        self._name = name
        self._actions = actions

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 switch program is on."""
        return bool(self.value)

    def turn_on(self, **kwargs) -> None:
        """Send the turn on command to the ISY994 switch program."""
        if not self._actions.runThen():
            _LOGGER.error('Unable to turn on switch')

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch program."""
        if not self._actions.runElse():
            _LOGGER.error('Unable to turn off switch')
