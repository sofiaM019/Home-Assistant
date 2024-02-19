"""Tests for myuplink switch module."""

from unittest.mock import MagicMock

from aiohttp import ClientError
import pytest

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

TEST_PLATFORM = Platform.SWITCH
pytestmark = pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)])

ENTITY_ID = "switch.f730_cu_3x400v_temporary_lux"
ENTITY_FRIENDLY_NAME = "F730 CU 3x400V Tempo­rary lux"
ENTITY_UID = "batman-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff-50004"


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test that the entities are registered in the entity registry."""

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == ENTITY_UID


async def test_attributes(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test the switch attributes are correct."""

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes == {
        "friendly_name": ENTITY_FRIENDLY_NAME,
        "icon": "mdi:water-alert-outline",
    }


async def test_switch_on(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test the switch can be turned on."""

    await hass.services.async_call(
        TEST_PLATFORM, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()
    mock_myuplink_client.async_set_device_points.assert_called_once()


async def test_switch_off(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test the switch can be turned on."""

    await hass.services.async_call(
        TEST_PLATFORM, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()
    mock_myuplink_client.async_set_device_points.assert_called_once()


async def test_api_failure(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test handling of exception from API."""

    with pytest.raises(HomeAssistantError):
        mock_myuplink_client.async_set_device_points.side_effect = ClientError
        await hass.services.async_call(
            TEST_PLATFORM, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
        await hass.async_block_till_done()
        mock_myuplink_client.async_set_device_points.assert_called_once()
