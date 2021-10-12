"""Config flow for Deluge Bittorent Client."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback

from . import get_client
from .const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .errors import AuthenticationError, CannotConnect, UnknownError

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class DelugeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Deluge config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return DelugeOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            for entry in self._async_current_entries():
                if (
                    entry.data[CONF_HOST] == user_input[CONF_HOST]
                    and entry.data[CONF_PORT] == user_input[CONF_PORT]
                ):
                    return self.async_abort(reason="already_configured")
                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    errors[CONF_NAME] = "name_exists"
                    break
            try:
                await get_client(self.hass, user_input)

            except AuthenticationError:
                errors[CONF_USERNAME] = "invalid_auth"
                errors[CONF_PASSWORD] = "invalid_auth"
            except (CannotConnect, UnknownError):
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Import from Deluge client config."""
        import_config[CONF_SCAN_INTERVAL] = import_config[
            CONF_SCAN_INTERVAL
        ].total_seconds()
        return await self.async_step_user(user_input=import_config)


class DelugeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Deluge client options."""

    def __init__(self, config_entry):
        """Initialize Deluge options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Deluge options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): int,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
