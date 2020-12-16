"""Config flow for the Jellyfin integration."""
import logging
import socket
import uuid

from jellyfin_apiclient_python import Jellyfin, JellyfinClient
from jellyfin_apiclient_python.connection_manager import CONNECTION_STATE
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components.jellyfin.const import (
    CLIENT_VERSION,
    DOMAIN,
    USER_AGENT,
    USER_APP_NAME,
)
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jellyfin."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a user defined configuration."""
        await self.async_set_unique_id(DOMAIN)

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                title = user_input.get(CONF_URL)
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


async def validate_input(hass: core.HomeAssistant, user_input: dict) -> JellyfinClient:
    """Validate that the provided url and credentials can be used to connect."""
    jellyfin = Jellyfin()
    client = jellyfin.get_client()
    _setup_client(client)

    url = user_input.get(CONF_URL)
    username = user_input.get(CONF_USERNAME)
    password = user_input.get(CONF_PASSWORD)

    await hass.async_add_executor_job(_connect, client, url, username, password)

    return client


def _setup_client(client: JellyfinClient):
    """Configure the Jellyfin client with a number of required properties."""
    player_name = socket.gethostname()
    client_uuid = str(uuid.uuid4())

    client.config.app(USER_APP_NAME, CLIENT_VERSION, player_name, client_uuid)
    client.config.http(USER_AGENT)


def _connect(client: JellyfinClient, url, username, password) -> bool:
    """Connect to the Jellyfin server and assert that the user can login."""
    client.config.data["auth.ssl"] = True if url.startswith("https") else False

    state = client.auth.connect_to_address(url)
    if state["State"] != CONNECTION_STATE["ServerSignIn"]:
        _LOGGER.error(
            "Unable to connect to: %s. Connection State: %s", url, state["State"]
        )
        raise CannotConnect

    response = client.auth.login(url, username, password)
    if "AccessToken" not in response:
        raise InvalidAuth

    return True


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate the server is unreachable."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate the credentials are invalid."""
