"""Tests for rainbird number platform."""

from http import HTTPStatus

import pytest

from homeassistant.components import number
from homeassistant.components.rainbird import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    ACK_ECHO,
    RAIN_DELAY,
    RAIN_DELAY_OFF,
    SERIAL_NUMBER,
    ComponentSetup,
    mock_response,
    mock_response_error,
)

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.NUMBER]


@pytest.mark.parametrize(
    ("rain_delay_response", "expected_state"),
    [(RAIN_DELAY, "16"), (RAIN_DELAY_OFF, "0")],
)
async def test_number_values(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    expected_state: str,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number platform."""

    assert await setup_integration()

    raindelay = hass.states.get("number.rain_bird_controller_rain_delay")
    assert raindelay is not None
    assert raindelay.state == expected_state
    assert raindelay.attributes == {
        "friendly_name": "Rain Bird Controller Rain delay",
        "icon": "mdi:water-off",
        "min": 0,
        "max": 14,
        "mode": "auto",
        "step": 1,
        "unit_of_measurement": "d",
    }

    entity = entity_registry.async_get("number.rain_bird_controller_rain_delay")
    assert entity
    assert entity.unique_id == "1263613994342-rain-delay"


async def test_set_value(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[str],
    config_entry: ConfigEntry,
) -> None:
    """Test setting the rain delay number."""

    assert await setup_integration()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, SERIAL_NUMBER)})
    assert device
    assert device.name == "Rain Bird Controller"
    assert device.model == "ESP-TM2"
    assert device.sw_version == "9.12"

    aioclient_mock.mock_calls.clear()
    responses.append(mock_response(ACK_ECHO))

    await hass.services.async_call(
        number.DOMAIN,
        number.SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.rain_bird_controller_rain_delay",
            number.ATTR_VALUE: 3,
        },
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1


@pytest.mark.parametrize(
    ("status", "expected_msg"),
    [
        (HTTPStatus.SERVICE_UNAVAILABLE, "Rain Bird device is busy"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "Rain Bird device failure"),
    ],
)
async def test_set_value_error(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[str],
    config_entry: ConfigEntry,
    status: HTTPStatus,
    expected_msg: str,
) -> None:
    """Test an error while talking to the device."""

    assert await setup_integration()

    aioclient_mock.mock_calls.clear()
    responses.append(mock_response_error(status=status))

    with pytest.raises(HomeAssistantError, match=expected_msg):
        await hass.services.async_call(
            number.DOMAIN,
            number.SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.rain_bird_controller_rain_delay",
                number.ATTR_VALUE: 3,
            },
            blocking=True,
        )

    assert len(aioclient_mock.mock_calls) == 1


@pytest.mark.parametrize(
    ("config_entry_unique_id"),
    [
        (None),
    ],
)
async def test_no_unique_id(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number platform with no unique id."""

    assert await setup_integration()

    raindelay = hass.states.get("number.rain_bird_controller_rain_delay")
    assert raindelay is not None
    assert (
        raindelay.attributes.get("friendly_name") == "Rain Bird Controller Rain delay"
    )

    entity = entity_registry.async_get("number.rain_bird_controller_rain_delay")
    assert not entity
