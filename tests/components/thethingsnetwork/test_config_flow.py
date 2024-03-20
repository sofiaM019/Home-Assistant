"""Define tests for the The Things Network onfig flows."""

from ttn_client import TTNAuthError

from homeassistant.components.thethingsnetwork.const import (
    CONF_API_KEY,
    CONF_APP_ID,
    CONF_HOSTNAME,
    DOMAIN,
    TTN_API_HOSTNAME,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY, APP_ID, CONFIG_ENTRY, HOSTNAME

USER_DATA = {CONF_HOSTNAME: HOSTNAME, CONF_APP_ID: APP_ID, CONF_API_KEY: API_KEY}
USER_DATA_PARTIAL = {CONF_APP_ID: APP_ID, CONF_API_KEY: API_KEY}


async def test_user(
    hass: HomeAssistant, mock_TTNClient_coordinator, mock_TTNClient_config_flow
) -> None:
    """Test user config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    user_data = result["data_schema"](USER_DATA_PARTIAL)
    assert user_data[CONF_HOSTNAME] == TTN_API_HOSTNAME  # Default value

    user_data[CONF_HOSTNAME] = HOSTNAME  # Change default value

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_data,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == APP_ID
    assert result["data"][CONF_HOSTNAME] == HOSTNAME
    assert result["data"][CONF_APP_ID] == APP_ID
    assert result["data"][CONF_API_KEY] == API_KEY

    # Connection error
    mock_TTNClient_config_flow.return_value.fetch_data.side_effect = TTNAuthError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_data,
    )
    assert result["type"] == FlowResultType.FORM
    assert "base" in result["errors"]


async def test_step_reauth(
    hass: HomeAssistant, mock_TTNClient_coordinator, mock_TTNClient_config_flow
) -> None:
    """Test that the reauth step works."""

    CONFIG_ENTRY.add_to_hass(hass)
    assert await hass.config_entries.async_setup(CONFIG_ENTRY.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": APP_ID,
            "entry_id": CONFIG_ENTRY.entry_id,
        },
        data=USER_DATA,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    user_data = result["data_schema"]({})
    assert user_data[CONF_API_KEY] == API_KEY  # Default value
    new_api_key = "1234"
    user_data[CONF_API_KEY] = new_api_key  # Change default value

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_data
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert hass.config_entries.async_entries()[0].data[CONF_API_KEY] == new_api_key
    await hass.async_block_till_done()
