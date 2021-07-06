"""Config flow to configure the Notion integration."""
from __future__ import annotations

from aionotion import async_get_client
from aionotion.errors import NotionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN


class NotionFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Notion config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data_schema = vol.Schema(
            {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
        )

    async def _show_form(self, errors: dict | None = None) -> FlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=self.data_schema, errors=errors or {}
        )

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            await async_get_client(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session
            )
        except NotionError:
            return await self._show_form({"base": "invalid_auth"})

        return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
