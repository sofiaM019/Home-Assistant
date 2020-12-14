"""Config flow for ReCollect Waste integration."""
from typing import Optional

from aiorecollect.client import Client
from aiorecollect.errors import RecollectError
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_POLL,
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_FRIENDLY_NAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import (  # pylint:disable=unused-import
    CONF_PLACE_ID,
    CONF_SERVICE_ID,
    DOMAIN,
    LOGGER,
)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_PLACE_ID): str, vol.Required(CONF_SERVICE_ID): str}
)


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ReCollect Waste."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "OptionsFlow":
        """Define the config flow to handle options."""
        return RecollectWasteOptionsFlowHandler(config_entry)

    async def async_step_import(self, import_config: dict = None) -> dict:
        """Handle configuration via YAML import."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input: dict = None) -> dict:
        """Handle configuration via the UI."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors={}
            )

        unique_id = f"{user_input[CONF_PLACE_ID]}, {user_input[CONF_SERVICE_ID]}"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        session = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(
            user_input[CONF_PLACE_ID], user_input[CONF_SERVICE_ID], session=session
        )

        try:
            await client.async_get_next_pickup_event()
        except RecollectError as err:
            LOGGER.error("Error during setup of integration: %s", err)
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={"base": "invalid_place_or_service_id"},
            )

        return self.async_create_entry(
            title=unique_id,
            data={
                CONF_PLACE_ID: user_input[CONF_PLACE_ID],
                CONF_SERVICE_ID: user_input[CONF_SERVICE_ID],
            },
        )


class RecollectWasteOptionsFlowHandler(OptionsFlow):
    """Handle a Recollect Waste options flow."""

    def __init__(self, entry: ConfigEntry):
        """Initialize."""
        self._entry = entry

    async def async_step_init(self, user_input: Optional[dict] = None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FRIENDLY_NAME,
                        default=self._entry.options.get(CONF_FRIENDLY_NAME),
                    ): bool
                }
            ),
        )
