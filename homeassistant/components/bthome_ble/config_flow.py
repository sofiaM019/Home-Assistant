"""Config flow for BThome Bluetooth integration."""
from __future__ import annotations

from collections.abc import Mapping
import dataclasses
import logging
from typing import Any

from bthome_ble import BThomeBluetoothDeviceData as DeviceData
from bthome_ble.parser import EncryptionScheme
import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class Discovery:
    """A discovered bluetooth device."""

    title: str
    discovery_info: BluetoothServiceInfo
    device: DeviceData


def _title(discovery_info: BluetoothServiceInfo, device: DeviceData) -> str:
    return device.title or device.get_device_name() or discovery_info.name


class BThomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BThome Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfo | None = None
        self._discovered_device: DeviceData | None = None
        self._discovered_devices: dict[str, Discovery] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = DeviceData()
        _LOGGER.error("Supported %s", device.supported(discovery_info))
        if not device.supported(discovery_info):
            _LOGGER.error("NOT SUPPORTED")
            return self.async_abort(reason="not_supported")
        _LOGGER.error("Hier ben ik")
        title = _title(discovery_info, device)
        self.context["title_placeholders"] = {"name": title}
        self._discovery_info = discovery_info
        self._discovered_device = device

        if device.encryption_scheme == EncryptionScheme.BTHOME_BINDKEY:
            return await self.async_step_get_encryption_key()
        return await self.async_step_bluetooth_confirm()

    async def async_step_get_encryption_key(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Enter a bindkey for an encrypted BThome device."""
        assert self._discovery_info
        assert self._discovered_device
        _LOGGER.error("Encryption key decoding")
        errors = {}

        if user_input is not None:
            bindkey = user_input["bindkey"]

            if len(bindkey) != 32:
                errors["bindkey"] = "expected_32_characters"
            else:
                self._discovered_device.bindkey = bytes.fromhex(bindkey)

                # If we got this far we already know supported will
                # return true so we don't bother checking that again
                # We just want to retry the decryption
                self._discovered_device.supported(self._discovery_info)

                if self._discovered_device.bindkey_verified:
                    return self._async_get_or_create_entry(bindkey)

                errors["bindkey"] = "decryption_failed"

        return self.async_show_form(
            step_id="get_encryption_key",
            description_placeholders=self.context["title_placeholders"],
            data_schema=vol.Schema({vol.Required("bindkey"): vol.All(str, vol.Strip)}),
            errors=errors,
        )

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        _LOGGER.error("BT confirm")
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self._async_get_or_create_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            discovery = self._discovered_devices[address]

            self.context["title_placeholders"] = {"name": discovery.title}

            self._discovery_info = discovery.discovery_info
            self._discovered_device = discovery.device

            if discovery.device.encryption_scheme == EncryptionScheme.BTHOME_BINDKEY:
                return await self.async_step_get_encryption_key()

            return self._async_get_or_create_entry()

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = DeviceData()
            if device.supported(discovery_info):
                self._discovered_devices[address] = Discovery(
                    title=_title(discovery_info, device),
                    discovery_info=discovery_info,
                    device=device,
                )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = {
            address: discovery.title
            for (address, discovery) in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(titles)}),
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle a flow initialized by a reauth event."""
        _LOGGER.error("Reauthing")
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None

        device: DeviceData = entry_data["device"]
        self._discovered_device = device

        self._discovery_info = device.last_service_info

        if device.encryption_scheme == EncryptionScheme.BTHOME_BINDKEY:
            return await self.async_step_get_encryption_key()

        # Otherwise there wasn't actually encryption so abort
        return self.async_abort(reason="reauth_successful")

    def _async_get_or_create_entry(self, bindkey=None):
        data = {}

        if bindkey:
            data["bindkey"] = bindkey

        if entry_id := self.context.get("entry_id"):
            entry = self.hass.config_entries.async_get_entry(entry_id)
            assert entry is not None

            self.hass.config_entries.async_update_entry(entry, data=data)

            # Reload the config entry to notify of updated config
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=self.context["title_placeholders"]["name"],
            data=data,
        )
