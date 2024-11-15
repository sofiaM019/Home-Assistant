"""Test binary sensors for acaia integration."""

from unittest.mock import MagicMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the acaia binary sensors."""

    with patch("homeassistant.components.acaia.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_only_connectivity_available(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test only connectivity is available if scale unavailable."""
    mock_scale.connected = False
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.lunar_ddeeff_timer_running")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("binary_sensor.lunar_ddeeff_connectivity")
    assert state
    assert state.state != STATE_UNAVAILABLE
