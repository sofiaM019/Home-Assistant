"""Config flow for Overkiz (by Somfy) integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from pyoverkiz.client import OverkizClient
from pyoverkiz.const import SUPPORTED_SERVERS
from pyoverkiz.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    TooManyRequestsException,
)
from pyoverkiz.models import obfuscate_id
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import device_registry as dr

from .const import CONF_HUB, DEFAULT_HUB
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Overkiz (by Somfy)."""

    VERSION = 1

    async def async_validate_input(self, user_input: dict[str, Any]) -> FlowResult:
        """Validate user credentials."""
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        server = SUPPORTED_SERVERS[user_input[CONF_HUB]]

        async with OverkizClient(
            username=username, password=password, server=server
        ) as client:
            await client.login()

            # Set first gateway as unique id
            gateways = await client.get_gateways()
            if gateways:
                gateway_id = gateways[0].id
                await self.async_set_unique_id(gateway_id)

            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=username, data=user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step via config flow."""
        errors = {}

        if user_input:
            try:
                return await self.async_validate_input(user_input)
            except TooManyRequestsException:
                errors["base"] = "too_many_requests"
            except BadCredentialsException:
                errors["base"] = "invalid_auth"
            except (TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            except MaintenanceException:
                errors["base"] = "server_in_maintenance"
            except AbortFlow as abort_flow:
                raise abort_flow
            except Exception as exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception(exception)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_HUB, default=DEFAULT_HUB): vol.In(
                        {key: hub.name for key, hub in SUPPORTED_SERVERS.items()}
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo):
        """Handle DHCP discovery."""
        hostname = discovery_info.hostname
        gateway_id = hostname[8:22]

        _LOGGER.debug("DHCP discovery detected gateway %s", obfuscate_id(gateway_id))

        if self._gateway_already_configured(gateway_id):
            _LOGGER.debug("Gateway %s is already configured", obfuscate_id(gateway_id))
            return self.async_abort(reason="already_configured")

        return await self.async_step_user()

    def _gateway_already_configured(self, gateway_id: str):
        """See if we already have a gateway matching the id."""
        device_registry = dr.async_get(self.hass)
        return bool(
            device_registry.async_get_device(
                identifiers={(DOMAIN, gateway_id)}, connections=set()
            )
        )
