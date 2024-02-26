"""Config flow for WeatherflowCloud integration."""
from __future__ import annotations

from typing import Any

from aiohttp import ClientResponseError
import voluptuous as vol
from weatherflow4py.api import WeatherFlowRestAPI

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


async def _async_validate_api_token(api_token) -> bool:
    """Validate the API token."""

    async with WeatherFlowRestAPI(api_token) as api:
        await api.async_get_stations()

    return True


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WeatherFlowCloud."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        if user_input is None:
            return await self._show_setup_form(user_input)

        await self.async_set_unique_id(user_input[CONF_API_TOKEN])
        self._abort_if_unique_id_configured()

        # Validate Entry
        api_token = user_input[CONF_API_TOKEN]
        try:
            await _async_validate_api_token(api_token)
            return self.async_create_entry(
                title="Weatherflow REST",
                data={CONF_API_TOKEN: api_token},
            )
        except ClientResponseError as err:
            if err.status == 401:
                return await self._show_setup_form({"base": "invalid_api_key"})
            return await self._show_setup_form({"base": "cannot_connect"})

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors or {},
        )
