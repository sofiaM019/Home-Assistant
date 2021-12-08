"""Config flow for Legrand RFLC integration."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Final

import lc7001.aio
import voluptuous

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.dhcp import IP_ADDRESS, MAC_ADDRESS, DhcpServiceInfo
from homeassistant.const import CONF_AUTHENTICATION, CONF_HOST, CONF_PASSWORD

from .const import DOMAIN

_LOGGER: Final = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ConfigFlow for Legrand RFLC integration."""

    VERSION = 1

    HOST: Final = lc7001.aio.Connector.HOST

    ABORT_NO_DEVICES_FOUND: Final = "no_devices_found"
    ABORT_REAUTH_SUCCESSFUL: Final = "reauth_successful"

    ERROR_INVALID_HOST: Final = "invalid_host"
    ERROR_INVALID_AUTH: Final = "invalid_auth"

    # Automatic ssdp discovery does not help.

    # Automatic zeroconf discovery does not help.
    # Even though the device supports mDNS, it does not publish any services to discover.

    # Automatic dhcp discovery can detect conversations (udp port bootpc or bootps)
    # with network devices that present their hostname as 'Legrand LC7001'
    # with a manifest.json entry of
    #   "dhcp": [{"hostname": "legrand lc7001"}]
    # This will happen each time a Legrand LC7001 controller (re)boots.
    # Linux requires the hass process have an effective cap_net_raw capability (or be run as root)
    # for this to work.
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initiated by dhcp discovery."""
        # example discovery_info
        # {'ip': '192.168.0.1', 'hostname': 'legrand lc7001', 'macaddress': '0026ec000000'}
        try:
            resolutions = await asyncio.get_event_loop().getaddrinfo(self.HOST, None)
        except OSError as error:
            _LOGGER.warning("OS getaddrinfo %s error %s", self.HOST, error)
            return self.async_abort(reason=self.ABORT_NO_DEVICES_FOUND)
        address = discovery_info[IP_ADDRESS]
        if any(
            resolution[4][0] == address
            for resolution in resolutions
            if resolution[0] == socket.AF_INET
        ):
            await self.async_set_unique_id(
                discovery_info[MAC_ADDRESS].lower()
            )  # already_in_progress
            self._abort_if_unique_id_configured()  # already_configured
            # wait for user interaction in the next step
            return await self.async_step_user()
        _LOGGER.warning("%s does not resolve to discovered %s", self.HOST, address)
        return self.async_abort(reason=self.ABORT_NO_DEVICES_FOUND)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        host = self.HOST
        if user_input is not None:
            host = user_input[CONF_HOST]
            key = None
            kwargs = {"key": key, "loop_timeout": -1}
            if CONF_PASSWORD in user_input:
                key = kwargs["key"] = lc7001.aio.hash_password(
                    user_input[CONF_PASSWORD].encode()
                )
            try:
                mac = await lc7001.aio.Connector(host, **kwargs).loop()
            except OSError:
                errors[CONF_HOST] = self.ERROR_INVALID_HOST
            except lc7001.aio.Authenticator.Error:
                errors[CONF_PASSWORD] = self.ERROR_INVALID_AUTH
            else:
                unique_id = mac.lower()
                await self.async_set_unique_id(unique_id)  # already_in_progress
                self._abort_if_unique_id_configured()  # already_configured
                data = {CONF_HOST: host}
                if key is not None:
                    data[CONF_AUTHENTICATION] = key.hex()
                return self.async_create_entry(title=unique_id, data=data)

        # get user_input
        return self.async_show_form(
            step_id="user",
            data_schema=voluptuous.Schema(
                {
                    voluptuous.Required(CONF_HOST, default=host): str,
                    voluptuous.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any]
    ) -> data_entry_flow.FlowResult:
        """Perform reauth upon an API authentication error."""
        self._data = user_input
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle configuration by reauth."""
        host = self.HOST
        errors = {CONF_PASSWORD: self.ERROR_INVALID_AUTH}
        if user_input is None:
            host = self._data[CONF_HOST]
        else:
            key: bytes | None = None
            kwargs = {"key": key, "loop_timeout": -1}
            if CONF_HOST in user_input:
                host = user_input[CONF_HOST]
            if CONF_AUTHENTICATION in user_input:
                key = kwargs["key"] = bytes.fromhex(user_input[CONF_AUTHENTICATION])
            if CONF_PASSWORD in user_input:
                key = kwargs["key"] = lc7001.aio.hash_password(
                    user_input[CONF_PASSWORD].encode()
                )
            try:
                mac = await lc7001.aio.Connector(host, **kwargs).loop()
            except OSError:
                errors[CONF_HOST] = self.ERROR_INVALID_HOST
            except lc7001.aio.Authenticator.Error:
                pass
            else:
                if mac.lower() != self.unique_id:
                    _LOGGER.warning(
                        "Expected %s but found %s at %s",
                        self.unique_id,
                        mac.lower(),
                        self.HOST,
                    )
                    errors[CONF_HOST] = self.ERROR_INVALID_HOST
                else:
                    data = {CONF_HOST: host}
                    if key is not None:
                        data[CONF_AUTHENTICATION] = key.hex()
                    entry_id = self.context["entry_id"]
                    entry = self.hass.config_entries.async_get_entry(entry_id)
                    assert entry is not None
                    self.hass.config_entries.async_update_entry(entry, data=data)
                    self.hass.async_create_task(
                        self.hass.config_entries.async_setup(entry_id)
                    )
                    return self.async_abort(reason=self.ABORT_REAUTH_SUCCESSFUL)

        # get user_input
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=voluptuous.Schema(
                {
                    voluptuous.Required(CONF_HOST, default=host): str,
                    voluptuous.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
