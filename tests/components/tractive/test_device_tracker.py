"""Test the Tractive device tracker platform."""

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the sensor."""
    with patch(
        "homeassistant.components.tractive.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await init_integration(hass, mock_config_entry)
        mock_tractive_client.send_position_event(hass)
        mock_tractive_client.send_hardware_event(hass)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
