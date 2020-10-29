"""Config flow for Bosch Smart Home Controller integration."""
import logging

from boschshcpy import SHCSession
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST

from .const import CONF_SSL_CERTIFICATE, CONF_SSL_KEY
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_SSL_CERTIFICATE): str,
        vol.Required(CONF_SSL_KEY): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = await hass.async_add_executor_job(
        SHCSession,
        data[CONF_HOST],
        data[CONF_SSL_CERTIFICATE],
        data[CONF_SSL_KEY],
        True,
    )

    session_information = await hass.async_add_executor_job(session.acquire_information)
    if session_information is None:
        raise InvalidAuth

    if session_information.getMacAddress() is None:
        raise InvalidAuth

    return {"title": "Bosch SHC", "mac": session_information.getMacAddress()}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch SHC."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                # Check if already configured
                await self.async_set_unique_id(info["mac"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_SSL_CERTIFICATE: user_input[CONF_SSL_CERTIFICATE],
                        CONF_SSL_KEY: user_input[CONF_SSL_KEY],
                    },
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
