"""Tests for the devolo Home Network sensors."""
from unittest.mock import AsyncMock

from devolo_plc_api.exceptions.device import DeviceUnavailable
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN
from homeassistant.components.devolo_home_network.const import (
    CONNECTED_TO_ROUTER,
    LONG_UPDATE_INTERVAL,
)
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import configure_integration
from .const import PLCNET_ATTACHED
from .mock import MockDevice

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("mock_device")
async def test_binary_sensor_setup(hass: HomeAssistant) -> None:
    """Test default setup of the binary sensor component."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.states.get(f"{DOMAIN}.{device_name}_{CONNECTED_TO_ROUTER}")

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_attached_to_router(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test state change of a attached_to_router binary sensor device."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{DOMAIN}.{device_name}_{CONNECTED_TO_ROUTER}"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(state_key))
    assert state == snapshot
    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    # Emulate device failure
    mock_device.plcnet.async_get_network_overview = AsyncMock(
        side_effect=DeviceUnavailable
    )
    async_fire_time_changed(hass, dt_util.utcnow() + LONG_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert (state := hass.states.get(state_key))
    assert state.state == STATE_UNAVAILABLE

    # Emulate state change
    mock_device.plcnet.async_get_network_overview = AsyncMock(
        return_value=PLCNET_ATTACHED
    )
    async_fire_time_changed(hass, dt_util.utcnow() + LONG_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert (state := hass.states.get(state_key))
    assert state.state == STATE_ON

    await hass.config_entries.async_unload(entry.entry_id)
