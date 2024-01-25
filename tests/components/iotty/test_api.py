"""Unit tests for iottycloud API."""


from unittest.mock import patch

from aiohttp import ClientSession
import pytest

from homeassistant.components.iotty import api
from homeassistant.components.iotty.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_api_create_fail(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test API creation with no session."""

    with pytest.raises(ValueError) as excinfo:
        _ = api.IottyProxy(hass, None, None)
    assert "websession" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        _ = api.IottyProxy(hass, aioclient_mock, None)
    assert "oauth_session" in str(excinfo.value)


async def test_api_create_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aiohttp_client_session: None,
    local_oauth_impl: ClientSession,
) -> None:
    """Test API creation."""

    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data["auth_implementation"] is not None

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, local_oauth_impl)

    assert iotty is not None


@patch(
    "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.valid_token", False
)
async def test_api_getaccesstoken_tokennotvalid_reloadtoken(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_aioclient: None,
    aiohttp_client_session: ClientSession,
) -> None:
    """Print a message if the token is not valid."""
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )
    mock_aioclient.post(
        "https://token.url", json={"access_token": "ACCESS_TOKEN_1", "expires_in": 100}
    )

    mock_aioclient.post("https://example.com", status=201)

    mock_config_entry.add_to_hass(hass)
    oauth2_session = config_entry_oauth2_flow.OAuth2Session(
        hass, mock_config_entry, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, oauth2_session)

    tok = await iotty.async_get_access_token()
    assert tok is not None
