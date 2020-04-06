"""Config flow to configure the Azure DevOps integration."""
import logging

from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.azure_devops.const import (
    CONF_ORG,
    CONF_PAT,
    CONF_PROJECT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigFlow

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class AzureDevOpsFlowHandler(ConfigFlow):
    """Handle a Azure DevOps config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    _hassio_discovery = None

    def __init__(self):
        """Initialize Azure DevOps flow."""
        pass

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ORG): str,
                    vol.Required(CONF_PROJECT): str,
                    vol.Required(CONF_PAT): str,
                }
            ),
            errors=errors or {},
        )

    async def _show_hassio_form(self, errors=None):
        """Show the Hass.io confirmation form to the user."""
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
            data_schema=vol.Schema({}),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        connection = Connection(
            base_url=f"https://dev.azure.com/{user_input.get(CONF_ORG)}",
            creds=BasicAuthentication("", user_input.get(CONF_PAT)),
        )
        client = connection.clients.get_core_client()

        project = client.get_project(user_input.get(CONF_PROJECT))

        if not project:
            _LOGGER.error(
                "Could not get project %s with Azure DevOps.",
                user_input.get(CONF_PROJECT),
            )
            return False

        return self.async_create_entry(
            title=f"{user_input.get(CONF_ORG)}/{user_input.get(CONF_PROJECT)}",
            data={
                CONF_ORG: user_input.get(CONF_ORG),
                CONF_PROJECT: user_input.get(CONF_PROJECT),
                CONF_PAT: user_input.get(CONF_PAT),
            },
        )
