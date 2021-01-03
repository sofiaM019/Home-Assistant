"""Config flow for roon integration."""
import asyncio
import logging

from roonapi import RoonApi, RoonDiscovery
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_API_KEY, CONF_HOST

from .const import (  # pylint: disable=unused-import
    AUTHENTICATE_TIMEOUT,
    CONF_ROON_ID,
    DEFAULT_NAME,
    DOMAIN,
    ROON_APPINFO,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({"host": str})

TIMEOUT = 120


class RoonHub:
    """Interact with roon during config flow."""

    def discover(self):
        """Try and discover roon servers."""
        discovery = RoonDiscovery(None)
        servers = discovery.all()
        _LOGGER.debug("Servers = %s", servers)
        discovery.stop()
        return servers

    async def authenticate(self, hass, host, servers):
        """Authenticate with one or more roon servers."""
        token = None
        core_id = None
        secs = 0
        if host is None:
            apis = [
                RoonApi(ROON_APPINFO, None, server[0], server[1], blocking_init=False)
                for server in servers
            ]
        else:
            apis = [RoonApi(ROON_APPINFO, None, host, blocking_init=False)]

        while secs < TIMEOUT:
            # Roon can discover multiple devices - not all of which are proper servers, so try and authenticate with them all.
            # The user will only enable one - so look for a valid token
            auth_api = [api for api in apis if api.token is not None]

            secs += AUTHENTICATE_TIMEOUT
            if len(auth_api) > 0:
                core_id = auth_api[0].core_id
                token = auth_api[0].token
                break

            await asyncio.sleep(AUTHENTICATE_TIMEOUT)

        for api in apis:
            api.stop()

        return (token, core_id)


async def discover():
    """Connect and authenticate home assistant."""

    hub = RoonHub()
    servers = hub.discover()

    return servers


async def authenticate(hass: core.HomeAssistant, host, servers):
    """Connect and authenticate home assistant."""

    hub = RoonHub()
    (token, core_id) = await hub.authenticate(hass, host, servers)
    if token is None:
        raise InvalidAuth

    return {CONF_HOST: host, CONF_ROON_ID: core_id, CONF_API_KEY: token}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for roon."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Roon flow."""
        self._host = None
        self._servers = []

    async def async_step_user(self, user_input=None):
        """Handle getting host details from the user."""

        errors = {}
        self._servers = await discover()

        # We discovered one or more  roon - so skip to authentication
        if len(self._servers) > 0:
            return await self.async_step_link()

        if user_input is not None:
            self._host = user_input["host"]
            existing = {
                entry.data[CONF_HOST] for entry in self._async_current_entries()
            }
            if self._host in existing:
                errors["base"] = "duplicate_entry"
                return self.async_show_form(step_id="user", errors=errors)

            return await self.async_step_link()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_link(self, user_input=None):
        """Handle linking and authenticting with the roon server."""

        errors = {}
        if user_input is not None:
            try:
                info = await authenticate(self.hass, self._host, self._servers)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=info)

        return self.async_show_form(step_id="link", errors=errors)


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
