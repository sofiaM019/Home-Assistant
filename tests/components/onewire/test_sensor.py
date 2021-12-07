"""Tests for 1-Wire sensor platform."""
from copy import deepcopy
import logging
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_STATE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import ensure_list

from . import (
    check_and_enable_disabled_entities,
    check_device_registry,
    check_entities,
    setup_owproxy_mock_devices,
    setup_sysbus_mock_devices,
)
from .const import (
    ATTR_DEFAULT_DISABLED,
    ATTR_DEVICE_FILE,
    ATTR_DEVICE_INFO,
    ATTR_STATE_CLONE,
    ATTR_UNIQUE_ID,
    ATTR_UNKNOWN_DEVICE,
    MOCK_OWPROXY_DEVICES,
    MOCK_SYSBUS_DEVICES,
)

from tests.common import mock_device_registry, mock_registry


@pytest.fixture(autouse=True)
def override_platforms():
    """Override PLATFORMS."""
    with patch("homeassistant.components.onewire.PLATFORMS", [Platform.SENSOR]):
        yield


def _clone_for_raw_value(expected_entity: dict) -> dict:
    new_entity = deepcopy(expected_entity)
    new_entity.update(
        {
            ATTR_DEFAULT_DISABLED: True,
            ATTR_DEVICE_FILE: expected_entity.get(
                ATTR_DEVICE_FILE, expected_entity[ATTR_UNIQUE_ID]
            ),
            ATTR_ENTITY_ID: f"{expected_entity[ATTR_ENTITY_ID]}_raw_value",
            ATTR_STATE: expected_entity.get(
                ATTR_STATE_CLONE, expected_entity[ATTR_STATE]
            ),
            ATTR_UNIQUE_ID: f"{expected_entity[ATTR_UNIQUE_ID]}_raw_value",
        }
    )
    return new_entity


async def test_owserver_sensor(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    owproxy: MagicMock,
    device_id: str,
    caplog: pytest.LogCaptureFixture,
):
    """Test for 1-Wire device.

    As they would be on a clean setup: all binary-sensors and switches disabled.
    """
    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    mock_device = MOCK_OWPROXY_DEVICES[device_id]
    device_entities = mock_device.get(Platform.SENSOR, [])
    if "branches" in mock_device:
        for branch_details in mock_device["branches"].values():
            for sub_device in branch_details.values():
                device_entities += sub_device[Platform.SENSOR]
    expected_devices = ensure_list(mock_device.get(ATTR_DEVICE_INFO))

    expected_entities = list(device_entities)
    for expected_entity in device_entities:
        if ATTR_STATE_CLONE in expected_entity:
            expected_entities.append(_clone_for_raw_value(expected_entity))

    setup_owproxy_mock_devices(owproxy, Platform.SENSOR, [device_id])
    with caplog.at_level(logging.WARNING, logger="homeassistant.components.onewire"):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        if mock_device.get(ATTR_UNKNOWN_DEVICE):
            assert "Ignoring unknown device family/type" in caplog.text
        else:
            assert "Ignoring unknown device family/type" not in caplog.text

    check_device_registry(device_registry, expected_devices)
    assert len(entity_registry.entities) == len(expected_entities)
    check_and_enable_disabled_entities(entity_registry, expected_entities)

    setup_owproxy_mock_devices(owproxy, Platform.SENSOR, [device_id])
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    check_entities(hass, entity_registry, expected_entities)


@pytest.mark.usefixtures("sysbus")
@pytest.mark.parametrize("device_id", MOCK_SYSBUS_DEVICES.keys(), indirect=True)
async def test_onewiredirect_setup_valid_device(
    hass: HomeAssistant,
    sysbus_config_entry: ConfigEntry,
    device_id: str,
    caplog: pytest.LogCaptureFixture,
):
    """Test that sysbus config entry works correctly."""
    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    glob_result, read_side_effect = setup_sysbus_mock_devices(
        Platform.SENSOR, [device_id]
    )

    mock_device = MOCK_SYSBUS_DEVICES[device_id]
    device_entities = mock_device.get(Platform.SENSOR, [])
    expected_devices = ensure_list(mock_device.get(ATTR_DEVICE_INFO))

    expected_entities = list(device_entities)
    for expected_entity in device_entities:
        expected_entities.append(_clone_for_raw_value(expected_entity))

    with patch("pi1wire._finder.glob.glob", return_value=glob_result,), patch(
        "pi1wire.OneWire.get_temperature",
        side_effect=read_side_effect,
    ), caplog.at_level(
        logging.WARNING, logger="homeassistant.components.onewire"
    ), patch(
        "homeassistant.components.onewire.sensor.asyncio.sleep"
    ):
        await hass.config_entries.async_setup(sysbus_config_entry.entry_id)
        await hass.async_block_till_done()
        assert "No onewire sensor found. Check if dtoverlay=w1-gpio" not in caplog.text
        if mock_device.get(ATTR_UNKNOWN_DEVICE):
            assert "Ignoring unknown device family" in caplog.text
        else:
            assert "Ignoring unknown device family" not in caplog.text

    check_device_registry(device_registry, expected_devices)
    assert len(entity_registry.entities) == len(expected_entities)
    check_and_enable_disabled_entities(entity_registry, expected_entities)

    with patch("pi1wire._finder.glob.glob", return_value=glob_result,), patch(
        "pi1wire.OneWire.get_temperature",
        side_effect=read_side_effect,
    ), patch("homeassistant.components.onewire.sensor.asyncio.sleep"):
        await hass.config_entries.async_reload(sysbus_config_entry.entry_id)
        await hass.async_block_till_done()

    check_entities(hass, entity_registry, expected_entities)
