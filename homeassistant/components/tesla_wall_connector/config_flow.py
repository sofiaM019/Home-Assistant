"""Config flow for Tesla Wall Connector integration."""
from __future__ import annotations

import logging
from typing import Any

from tesla_wall_connector import WallConnector
from tesla_wall_connector.exceptions import WallConnectorError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.dhcp import IP_ADDRESS
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_SCAN_INTERVAL_CHARGING,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_CHARGING,
    DOMAIN,
    WALLCONNECTOR_DEVICE_NAME,
    WALLCONNECTOR_SERIAL_NUMBER,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    wall_connector = WallConnector(
        host=data[CONF_HOST], session=async_get_clientsession(hass)
    )
    try:
        version = await wall_connector.async_get_version()
    except WallConnectorError as ex:
        raise CannotConnect from ex

    return {
        "title": WALLCONNECTOR_DEVICE_NAME,
        WALLCONNECTOR_SERIAL_NUMBER: version.serial_number,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tesla Wall Connector."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self.ip_address = None
        self.serial_number = None

    async def async_step_dhcp(self, discovery_info):
        """Handle dhcp discovery."""
        self.ip_address = discovery_info[IP_ADDRESS]
        _LOGGER.info("Discovered Tesla Wall Connector at [%s]", self.ip_address)

        try:
            wall_connector = WallConnector(
                host=self.ip_address, session=async_get_clientsession(self.hass)
            )
            version = await wall_connector.async_get_version()
            self.serial_number = version.serial_number
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Could not read serial number from Tesla WallConnector at [%s]: [%s]",
                self.ip_address,
                ex,
            )

        self._async_abort_entries_match({CONF_HOST: self.ip_address})

        _LOGGER.info(
            "No entry found for wall connector with IP %s. Serial nr: %s",
            str(self.ip_address),
            str(self.serial_number),
        )

        self.context["description_placeholders"] = {CONF_HOST: self.ip_address}
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        data_schema = vol.Schema(
            {vol.Required(CONF_HOST, default=self.ip_address): str}
        )
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)
        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if not errors:
            existing_entry = await self.async_set_unique_id(
                info[WALLCONNECTOR_SERIAL_NUMBER]
            )
            if existing_entry:
                self.hass.config_entries.async_update_entry(
                    existing_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="already_configured")

            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Tesla Wall Connector."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Clamp(min=1)),
                vol.Optional(
                    CONF_SCAN_INTERVAL_CHARGING,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL_CHARGING, DEFAULT_SCAN_INTERVAL_CHARGING
                    ),
                ): vol.All(vol.Coerce(int), vol.Clamp(min=1)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
