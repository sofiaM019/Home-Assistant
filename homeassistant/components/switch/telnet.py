"""
Support for switch controlled using a telnet connection.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.telnet/
"""
import logging
import telnetlib
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA,
                                             ENTITY_ID_FORMAT)
from homeassistant.const import (
    CONF_RESOURCE, CONF_FRIENDLY_NAME, CONF_OPTIMISTIC, CONF_SWITCHES,
    CONF_VALUE_TEMPLATE, CONF_COMMAND_OFF, CONF_COMMAND_ON, CONF_COMMAND_STATE)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SWITCH_SCHEMA = vol.Schema({
    vol.Required(CONF_RESOURCE): cv.string,
    vol.Required(CONF_COMMAND_OFF): cv.string,
    vol.Required(CONF_COMMAND_ON): cv.string,
    vol.Optional(CONF_COMMAND_STATE): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_OPTIMISTIC): cv.boolean,
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SWITCHES): vol.Schema({cv.slug: SWITCH_SCHEMA}),
})

SCAN_INTERVAL = timedelta(seconds=10)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return switches controlled by shell commands."""
    devices = config.get(CONF_SWITCHES, {})
    switches = []

    for object_id, device_config in devices.items():
        value_template = device_config.get(CONF_VALUE_TEMPLATE)

        if value_template is not None:
            value_template.hass = hass

        switches.append(
            TelnetSwitch(
                hass,
                object_id,
                device_config.get(CONF_RESOURCE),
                device_config.get(CONF_FRIENDLY_NAME, object_id),
                device_config.get(CONF_COMMAND_ON),
                device_config.get(CONF_COMMAND_OFF),
                device_config.get(CONF_COMMAND_STATE),
                device_config.get(CONF_OPTIMISTIC),
                value_template
            )
        )

    if not switches:
        _LOGGER.error("No switches added")
        return False

    add_devices(switches)


class TelnetSwitch(SwitchDevice):
    """Representation of a switch that can be toggled using telnet commands."""

    def __init__(self, hass, object_id, resource, friendly_name, command_on,
                 command_off, command_state, optimistic, value_template):
        """Initialize the switch."""
        self._hass = hass
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._resource = resource
        self._name = friendly_name
        self._state = False
        self._command_on = command_on
        self._command_off = command_off
        self._command_state = command_state
        self._optimistic = optimistic
        self._value_template = value_template

    def __telnet_command(self, command):
        try:
            telnet = telnetlib.Telnet(self._resource)
            telnet.write(command.encode('ASCII') + b'\r')
            response = telnet.read_until(b'\r', timeout=0.2)
            return response.decode('ASCII').strip()
        except Exception as e:
            _LOGGER.error(
                'Command "%s" failed with exception: %s', command, repr(e))
            return None

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """Only poll if we have state command."""
        return self._command_state is not None

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Default ist true if no state command is defined, false otherwise."""
        if self._optimistic is not None:
            return self._optimistic

        return self._command_state is None

    def update(self):
        """Update device state."""
        response = self.__telnet_command(self._command_state)
        if response:
            _LOGGER.info(
                'command="%s" -> response="%s"', self._command_state, response)
            rendered = self._value_template \
                .render_with_possible_json_value(response)
            self._state = rendered == "True"

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.__telnet_command(self._command_on)
        if self._optimistic:
            self._state = True

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.__telnet_command(self._command_off)
        if self._optimistic:
            self._state = False
