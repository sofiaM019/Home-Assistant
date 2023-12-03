"""Config flow for StreamLabs integration."""
from __future__ import annotations

from typing import Any

from streamlabswater.streamlabswater import StreamlabsClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN, LOGGER

ISSUE_PLACEHOLDER = {"url": "/config/integrations/dashboard/add?domain=streamlabswater"}


async def validate_input(hass: HomeAssistant, api_key: str) -> None:
    """Validate the user input allows us to connect."""
    client = StreamlabsClient(api_key)
    response = await hass.async_add_executor_job(client.get_locations)
    locations = response.get("locations")

    if locations is None:
        raise CannotConnect


class StreamlabsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for StreamLabs."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            try:
                await validate_input(self.hass, user_input[CONF_API_KEY])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Streamlabs", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Import the yaml config."""
        try:
            self._async_abort_entries_match(user_input)
        except AbortFlow:
            async_create_issue(
                self.hass,
                DOMAIN,
                "deprecated_yaml_import_issue_already_configured",
                breaks_in_ha_version="2024.7.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml_import_issue_already_configured",
                translation_placeholders=ISSUE_PLACEHOLDER,
            )
            return self.async_abort(reason="already_configured")
        try:
            await validate_input(self.hass, user_input[CONF_API_KEY])
        except CannotConnect:
            async_create_issue(
                self.hass,
                DOMAIN,
                "deprecated_yaml_import_issue_cannot_connect",
                breaks_in_ha_version="2024.7.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml_import_issue_cannot_connect",
                translation_placeholders=ISSUE_PLACEHOLDER,
            )
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            async_create_issue(
                self.hass,
                DOMAIN,
                "deprecated_yaml_import_issue_unknown",
                breaks_in_ha_version="2024.7.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml_import_issue_unknown",
                translation_placeholders=ISSUE_PLACEHOLDER,
            )
            return self.async_abort(reason="unknown")
        return self.async_create_entry(title="Streamlabs", data=user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
