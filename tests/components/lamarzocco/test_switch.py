"""Tests for La Marzocco switches."""
from unittest.mock import MagicMock

from lmcloud.const import LaMarzoccoModel
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_main(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Main switch."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_main")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_main",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_power.mock_calls) == 1
    mock_lamarzocco.set_power.assert_called_once_with(False, None)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_main",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_power.mock_calls) == 2
    mock_lamarzocco.set_power.assert_called_with(True, None)


async def test_auto_on_off(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Auto On/Off switch."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_auto_on_off")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_auto_on_off",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off_global.mock_calls) == 1
    mock_lamarzocco.set_auto_on_off_global.assert_called_once_with(enable=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_auto_on_off",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off_global.mock_calls) == 2
    mock_lamarzocco.set_auto_on_off_global.assert_called_with(enable=True)


async def test_prebrew(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Prebrew switch."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_prebrew")

    if mock_lamarzocco.model_name == LaMarzoccoModel.GS3_MP:
        assert state is None
        return
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_prebrew",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_prebrew.mock_calls) == 1
    mock_lamarzocco.set_prebrew.assert_called_once_with(enabled=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_prebrew",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_prebrew.mock_calls) == 2
    mock_lamarzocco.set_prebrew.assert_called_with(enabled=True)


async def test_preinfusion(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Preinfusion switch."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_preinfusion")

    if mock_lamarzocco.model_name == LaMarzoccoModel.GS3_MP:
        assert state is None
        return

    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_preinfusion",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_preinfusion.mock_calls) == 1
    mock_lamarzocco.set_preinfusion.assert_called_once_with(enabled=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_preinfusion",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_preinfusion.mock_calls) == 2
    mock_lamarzocco.set_preinfusion.assert_called_with(enabled=False)


async def test_steam_boiler_enable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Steam Boiler switch."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_steam_boiler")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_steam_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam.mock_calls) == 1
    mock_lamarzocco.set_steam.assert_called_once_with(False, None)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_steam_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam.mock_calls) == 2
    mock_lamarzocco.set_steam.assert_called_with(True, None)


async def test_call_without_bluetooth_works(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that if not using bluetooth, the switch still works."""
    serial_number = mock_lamarzocco.serial_number
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    coordinator._use_bluetooth = False

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_steam_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam.mock_calls) == 1
    mock_lamarzocco.set_steam.assert_called_once_with(False, None)
