"""Config flow for the Velbus platform."""
from __future__ import annotations

from velbusaio.controller import Velbus
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import DOMAIN


@callback
def velbus_entries(hass: HomeAssistant):
    """Return connections for Velbus domain."""
    return {
        (entry.data[CONF_PORT]) for entry in hass.config_entries.async_entries(DOMAIN)
    }


class VelbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the velbus config flow."""
        self._errors: dict[str, str] = {}

    def _create_device(self, name: str, prt: str):
        """Create an entry async."""
        return self.async_create_entry(title=name, data={CONF_PORT: prt})

    async def _test_connection(self, prt):
        """Try to connect to the velbus with the port specified."""
        print(prt)
        try:
            controller = Velbus(prt)
            await controller.connect(True)
            controller.stop()
        except Exception:  # pylint: disable=broad-except
            self._errors[CONF_PORT] = "cannot_connect"
            print("HERE")
            return False
        print("HERE2")
        return True

    def _prt_in_configuration_exists(self, prt: str) -> bool:
        """Return True if port exists in configuration."""
        if prt in velbus_entries(self.hass):
            return True
        return False

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            name = slugify(user_input[CONF_NAME])
            prt = user_input[CONF_PORT]
            if not self._prt_in_configuration_exists(prt):
                if await self._test_connection(prt):
                    return self._create_device(name, prt)
            else:
                self._errors[CONF_PORT] = "already_configured"
        else:
            user_input = {}
            user_input[CONF_NAME] = ""
            user_input[CONF_PORT] = ""

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(CONF_PORT, default=user_input[CONF_PORT]): str,
                }
            ),
            errors=self._errors,
        )
