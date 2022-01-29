"""Config flow for Elk-M1 Control integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import elkm1_lib as elkm1
from elkm1_lib.discovery import ElkSystem
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import dhcp
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PREFIX,
    CONF_PROTOCOL,
    CONF_TEMPERATURE_UNIT,
    CONF_USERNAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.util import slugify

from . import async_wait_for_elk_to_sync
from .const import CONF_AUTO_CONFIGURE, DISCOVER_SCAN_TIMEOUT, DOMAIN
from .discovery import (
    async_discover_device,
    async_discover_devices,
    async_update_entry_from_discovery,
)

CONF_DEVICE = "device"

_LOGGER = logging.getLogger(__name__)

PROTOCOL_MAP = {
    "secure": "elks://",
    "TLS 1.2": "elksv1_2://",
    "non-secure": "elk://",
    "serial": "serial://",
}

VALIDATE_TIMEOUT = 35


async def validate_input(data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    userid = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)

    prefix = data[CONF_PREFIX]
    url = _make_url_from_data(data)
    requires_password = url.startswith("elks://") or url.startswith("elksv1_2")

    if requires_password and (not userid or not password):
        raise InvalidAuth

    elk = elkm1.Elk(
        {"url": url, "userid": userid, "password": password, "element_list": ["panel"]}
    )
    elk.connect()

    if not await async_wait_for_elk_to_sync(elk, VALIDATE_TIMEOUT, url):
        raise InvalidAuth

    device_name = data[CONF_PREFIX] if data[CONF_PREFIX] else "ElkM1"
    # Return info that you want to store in the config entry.
    return {"title": device_name, CONF_HOST: url, CONF_PREFIX: slugify(prefix)}


def _make_url_from_data(data):
    if host := data.get(CONF_HOST):
        return host

    protocol = PROTOCOL_MAP[data[CONF_PROTOCOL]]
    address = data[CONF_ADDRESS]
    return f"{protocol}{address}"


def _short_mac(mac_address: str) -> str:
    return mac_address.replace(":", "")[-6:]


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elk-M1 Control."""

    VERSION = 1

    def __init__(self):
        """Initialize the elkm1 config flow."""
        self.importing = False
        self._discovered_device: ElkSystem | None = None
        self._discovered_devices: dict[str, ElkSystem] = {}

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle discovery via dhcp."""
        self._discovered_device = ElkSystem(
            discovery_info.macaddress, discovery_info.ip, 0
        )
        return await self._async_handle_discovery()

    async def async_step_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle discovery."""
        self._discovered_device = ElkSystem(
            discovery_info["mac_address"],
            discovery_info["ip_address"],
            discovery_info["port"],
        )
        return await self._async_handle_discovery()

    async def _async_handle_discovery(self) -> FlowResult:
        """Handle any discovery."""
        device = self._discovered_device
        assert device is not None
        mac = dr.format_mac(device.mac_address)
        host = device.ip_address
        await self.async_set_unique_id(mac)
        for entry in self._async_current_entries(include_ignore=False):
            if (
                entry.unique_id == mac
                or urlparse(entry.data[CONF_HOST]).hostname == host
            ):
                if async_update_entry_from_discovery(self.hass, entry, device):
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(entry.entry_id)
                    )
                return self.async_abort(reason="already_configured")
        self.context[CONF_HOST] = host
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == host:
                return self.async_abort(reason="already_in_progress")
        if not device.port:
            if discovered_device := await async_discover_device(self.hass, host):
                self._discovered_device = discovered_device[0]
            else:
                return self.async_abort(reason="cannot_connect")
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        device = self._discovered_device
        placeholders = {
            "mac_address": _short_mac(device.mac_address),
            "ip_address": device.ip_address,
        }
        self.context["title_placeholders"] = placeholders
        return await self.async_step_connection()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            if mac := user_input[CONF_DEVICE]:
                await self.async_set_unique_id(mac, raise_on_progress=False)
                self._discovered_device = self._discovered_devices[mac]
            return await self.async_step_connection()

        current_unique_ids = self._async_current_ids()
        current_hosts = {
            urlparse(entry.data[CONF_HOST]).hostname
            for entry in self._async_current_entries(include_ignore=False)
        }
        discovered_devices = await async_discover_devices(
            self.hass, DISCOVER_SCAN_TIMEOUT
        )
        self._discovered_devices = {
            dr.format_mac(device.mac_address): device for device in discovered_devices
        }
        devices_name: dict[str | None, str] = {
            mac: f"{_short_mac(device.mac_address)} ({device.ip_address})"
            for mac, device in self._discovered_devices.items()
            if mac not in current_unique_ids and device.ip_address not in current_hosts
        }
        devices_name[None] = "Manual Entry"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def async_step_connection(self, user_input=None):
        """Handle connecting the device."""
        errors = {}
        if user_input is not None:
            if self._discovered_device is not None:
                user_input[CONF_ADDRESS] = self._discovered_device.ip_address
                user_input[CONF_PREFIX] = _short_mac(
                    self._discovered_device.mac_address
                )

            if self._url_already_configured(_make_url_from_data(user_input)):
                return self.async_abort(reason="address_already_configured")

            try:
                info = await validate_input(user_input)

            except asyncio.TimeoutError:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(user_input[CONF_PREFIX])
                self._abort_if_unique_id_configured()

                if self.importing:
                    return self.async_create_entry(title=info["title"], data=user_input)

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: info[CONF_HOST],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_AUTO_CONFIGURE: True,
                        CONF_TEMPERATURE_UNIT: user_input[CONF_TEMPERATURE_UNIT],
                        CONF_PREFIX: info[CONF_PREFIX],
                    },
                )

        base_schema = {
            vol.Required(CONF_PROTOCOL, default="secure"): vol.In(
                ["secure", "TLS 1.2", "non-secure", "serial"]
            ),
            vol.Optional(CONF_USERNAME, default=""): str,
            vol.Optional(CONF_PASSWORD, default=""): str,
            vol.Optional(CONF_TEMPERATURE_UNIT, default=TEMP_FAHRENHEIT): vol.In(
                [TEMP_FAHRENHEIT, TEMP_CELSIUS]
            ),
        }
        if self._discovered_device is not None:
            base_schema[vol.Required(CONF_ADDRESS)] = str
            base_schema[vol.Optional(CONF_PREFIX, default="")] = str

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(base_schema), errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        self.importing = True
        return await self.async_step_connection(user_input)

    def _url_already_configured(self, url):
        """See if we already have a elkm1 matching user input configured."""
        existing_hosts = {
            urlparse(entry.data[CONF_HOST]).hostname
            for entry in self._async_current_entries()
        }
        return urlparse(url).hostname in existing_hosts


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
