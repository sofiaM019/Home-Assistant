"""Tests for the TotalConnect config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.totalconnect.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.setup import async_setup_component

from .common import CONFIG_DATA, CONFIG_DATA_NO_USERCODES, USERNAME

from tests.common import MockConfigEntry


async def test_user(hass):
    """Test user step."""
    # user starts with no data entered, so show the user form
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=None,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_user_show_locations(hass):
    """Test user locations form."""
    # user/pass provided, so check if valid then ask for usercodes on locations form
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient.TotalConnectClient"
    ) as client_mock:
        client_mock.return_value.is_valid_credentials.return_value = True
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA_NO_USERCODES,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "locations"


async def test_abort_if_already_setup(hass):
    """Test abort if the account is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        unique_id=USERNAME,
    ).add_to_hass(hass)

    # Should fail, same USERNAME (flow)
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient.TotalConnectClient"
    ) as client_mock:
        client_mock.return_value.is_valid_credentials.return_value = True
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_login_failed(hass):
    """Test when we have errors during login."""
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient.TotalConnectClient"
    ) as client_mock:
        client_mock.return_value.is_valid_credentials.return_value = False
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_started(hass):
    """Test that reauth is started when we have login errors."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient",
        autospec=True,
    ) as mock_client, patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectConfigFlow.async_step_reauth"
    ) as mock_async_step_reauth:
        mock_client.return_value.is_valid_credentials.return_value = False
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()
    mock_client.assert_called_once()
    mock_async_step_reauth.assert_called_once()
