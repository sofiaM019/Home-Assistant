"""Support for command line notification services."""
import logging
import subprocess

import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_COMMAND, CONF_NAME
import homeassistant.helpers.config_validation as cv

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


# pylint: disable=unused-argument
def get_service(hass, config, discovery_info=None):
    """Get the Command Line notification service."""
    command = config[CONF_COMMAND]
    timeout = config[CONF_COMMAND_TIMEOUT]
    name = config[CONF_NAME]

    return CommandLineNotificationService(command, timeout, name)


class CommandLineNotificationService(BaseNotificationService):
    """Implement the notification service for the Command Line service."""

    def __init__(self, command, timeout, name):
        """Initialize the service."""
        self.command = command
        self._timeout = timeout
        self.name = name

    def send_message(self, message="", **kwargs):
        """Send a message to a command line."""
        try:
            proc = subprocess.Popen(
                self.command,
                universal_newlines=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,  # nosec # shell by design
            )

            stdout_data, stderr_data = proc.communicate(
                input=message, timeout=self._timeout
            )
            if proc.returncode != 0:
                _LOGGER.error("Command failed: %s", self.command)

            if stdout_data:
                _LOGGER.debug(
                    "Stdout of command_line notify '%s': return code: %s\n%s",
                    self.name,
                    proc.returncode,
                    stdout_data,
                )
            if stderr_data:
                _LOGGER.debug(
                    "Stderr of command_line notify '%s': return code: %s\n%s",
                    self.name,
                    proc.returncode,
                    stderr_data,
                )
        except subprocess.TimeoutExpired:
            _LOGGER.error("Timeout for command: %s", self.command)
        except subprocess.SubprocessError:
            _LOGGER.error("Error trying to exec command: %s", self.command)
