"""Tests for the JVC Projector binary sensor device."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

POWER_ID = "sensor.jvc_projector_power_status"


async def test_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Tests entity state is registered."""
    state = hass.states.get(POWER_ID)
    assert entity
    assert entity_registry.async_get(entity.entity_id)

    entity = hass.states.get(entity.entity_id)
    assert entity is not None
    assert entity.state == "standby"
