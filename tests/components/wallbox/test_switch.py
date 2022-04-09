"""Test Wallbox Lock component."""
import json

import pytest
import requests_mock

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.components.wallbox import InvalidAuth
from homeassistant.components.wallbox.const import CONF_STATUS_ID_KEY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.components.wallbox import entry, setup_integration
from tests.components.wallbox.const import (
    CONF_ERROR,
    CONF_JWT,
    CONF_MOCK_SWITCH_ENTITY_ID,
    CONF_STATUS,
    CONF_TTL,
    CONF_USER_ID,
)

authorisation_response = json.loads(
    json.dumps(
        {
            CONF_JWT: "fakekeyhere",
            CONF_USER_ID: 12345,
            CONF_TTL: 145656758,
            CONF_ERROR: "false",
            CONF_STATUS: 200,
        }
    )
)


async def test_wallbox_switch_class(hass: HomeAssistant) -> None:
    """Test wallbox switch class."""

    await setup_integration(hass)

    state = hass.states.get(CONF_MOCK_SWITCH_ENTITY_ID)
    assert state
    assert state.state == "off"

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/v3/chargers/12345/remote-action",
            json=json.loads(json.dumps({CONF_STATUS_ID_KEY: 193})),
            status_code=200,
        )

        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: CONF_MOCK_SWITCH_ENTITY_ID,
            },
            blocking=True,
        )

        await hass.services.async_call(
            "switch",
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: CONF_MOCK_SWITCH_ENTITY_ID,
            },
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_switch_class_connection_error(hass: HomeAssistant) -> None:
    """Test wallbox switch class connection error."""

    await setup_integration(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/v3/chargers/12345/remote-action",
            json=json.loads(json.dumps({CONF_STATUS_ID_KEY: 193})),
            status_code=404,
        )

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: CONF_MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )
        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: CONF_MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_switch_class_authentication_error(hass: HomeAssistant) -> None:
    """Test wallbox switch class connection error."""

    await setup_integration(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/v3/chargers/12345/remote-action",
            json=json.loads(json.dumps({CONF_STATUS_ID_KEY: 193})),
            status_code=403,
        )

        with pytest.raises(InvalidAuth):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: CONF_MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )
        with pytest.raises(InvalidAuth):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: CONF_MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )

    await hass.config_entries.async_unload(entry.entry_id)
