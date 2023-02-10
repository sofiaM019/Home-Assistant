"""Config flow for EDL21 integration."""
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SERIAL_PORT, DEFAULT_DEVICE_NAME, DOMAIN


class EDL21ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """EDL21 config flow."""

    VERSION = 1

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""

        self._async_abort_entries_match(
            {
                CONF_SERIAL_PORT: import_config[CONF_SERIAL_PORT],
            }
        )
        if import_config[CONF_NAME] != "":
            self._async_abort_entries_match(
                {
                    CONF_NAME: import_config[CONF_NAME],
                }
            )

        title = (
            import_config[CONF_NAME]
            if import_config[CONF_NAME] != ""
            else DEFAULT_DEVICE_NAME
        )

        return self.async_create_entry(
            title=title,
            data=import_config,
        )

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the user setup step."""
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT],
                }
            )
            self._async_abort_entries_match(
                {
                    CONF_NAME: user_input[CONF_NAME],
                }
            )

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        data_schema = {
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_SERIAL_PORT): str,
        }

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))
