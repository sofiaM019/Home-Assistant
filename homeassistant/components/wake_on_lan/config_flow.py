"""Config flow for Wake on lan integration."""

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    ActionSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import CONF_OFF_ACTION, DEFAULT_NAME, DOMAIN


async def validate(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate input."""
    if CONF_BROADCAST_PORT in user_input:
        # Convert float to int for broadcast port
        user_input[CONF_BROADCAST_PORT] = int(user_input[CONF_BROADCAST_PORT])

    user_input[CONF_MAC] = dr.format_mac(user_input[CONF_MAC])

    # Mac address needs to be unique
    handler.parent_handler._async_abort_entries_match({CONF_MAC: user_input[CONF_MAC]})  # noqa: SLF001

    return user_input


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): TextSelector(),
        vol.Optional(CONF_HOST): TextSelector(),
        vol.Optional(CONF_OFF_ACTION): ActionSelector(),
        vol.Optional(CONF_BROADCAST_ADDRESS): TextSelector(),
        vol.Optional(CONF_BROADCAST_PORT): NumberSelector(
            NumberSelectorConfig(min=0, max=65535, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(schema=DATA_SCHEMA, validate_user_input=validate),
    "import": SchemaFlowFormStep(schema=DATA_SCHEMA, validate_user_input=validate),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(DATA_SCHEMA, validate_user_input=validate),
}


class StatisticsConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Statistics."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        if CONF_NAME in options:
            # Only if imported
            return cast(str, options[CONF_NAME])
        mac: str = options[CONF_MAC]
        return f"{DEFAULT_NAME} {mac}"
