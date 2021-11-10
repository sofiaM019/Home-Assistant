"""Tests for the devolo Home Network switch."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from devolo_plc_api.exceptions.device import DeviceUnavailable
import pytest

from homeassistant.components.devolo_home_network.const import SHORT_UPDATE_INTERVAL
from homeassistant.components.switch import DOMAIN
from homeassistant.const import (
    ENTITY_CATEGORY_CONFIG,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.update_coordinator import REQUEST_REFRESH_DEFAULT_COOLDOWN
from homeassistant.util import dt

from . import configure_integration

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("mock_device")
@pytest.mark.usefixtures("mock_zeroconf")
async def test_switch_setup(hass: HomeAssistant):
    """Test default setup of the switch component."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.enable_guest_wifi") is not None
    assert hass.states.get(f"{DOMAIN}.enable_leds") is not None

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_device")
@pytest.mark.usefixtures("mock_zeroconf")
async def test_update_enable_guest_wifi(hass: HomeAssistant):
    """Test state change of a enable_guest_wifi switch device."""
    state_key = f"{DOMAIN}.enable_guest_wifi"

    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_OFF

    # Emulate state change
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_guest_access",
        new=AsyncMock(return_value={"enabled": True}),
    ):
        async_fire_time_changed(hass, dt.utcnow() + SHORT_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_ON

    # Switch off
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_guest_access",
        new=AsyncMock(return_value={"enabled": False}),
    ), patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_set_wifi_guest_access",
        new=AsyncMock(),
    ) as turn_off:
        await hass.services.async_call(
            DOMAIN, SERVICE_TURN_OFF, {"entity_id": state_key}, blocking=True
        )
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_OFF
        turn_off.assert_called_once_with(False)

    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=REQUEST_REFRESH_DEFAULT_COOLDOWN)
    )

    # Switch on
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_guest_access",
        new=AsyncMock(return_value={"enabled": True}),
    ), patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_set_wifi_guest_access",
        new=AsyncMock(),
    ) as turn_on:
        await hass.services.async_call(
            DOMAIN, SERVICE_TURN_ON, {"entity_id": state_key}, blocking=True
        )
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_ON
        turn_on.assert_called_once_with(True)

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_device")
@pytest.mark.usefixtures("mock_zeroconf")
async def test_update_enable_leds(hass: HomeAssistant):
    """Test state change of a enable_leds switch device."""
    state_key = f"{DOMAIN}.enable_leds"

    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_OFF

    er = entity_registry.async_get(hass)
    assert er.async_get(state_key).entity_category == ENTITY_CATEGORY_CONFIG

    # Emulate state change
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_led_setting",
        new=AsyncMock(return_value={"state": "LED_ON"}),
    ):
        async_fire_time_changed(hass, dt.utcnow() + SHORT_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_ON

    # Switch off
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_led_setting",
        new=AsyncMock(return_value={"state": "LED_OFF"}),
    ), patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_set_led_setting",
        new=AsyncMock(),
    ) as turn_off:
        await hass.services.async_call(
            DOMAIN, SERVICE_TURN_OFF, {"entity_id": state_key}, blocking=True
        )
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_OFF
        turn_off.assert_called_once_with(False)

    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=REQUEST_REFRESH_DEFAULT_COOLDOWN)
    )

    # Switch on
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_led_setting",
        new=AsyncMock(return_value={"state": "LED_ON"}),
    ), patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_set_led_setting",
        new=AsyncMock(),
    ) as turn_on:
        await hass.services.async_call(
            DOMAIN, SERVICE_TURN_ON, {"entity_id": state_key}, blocking=True
        )
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_ON
        turn_on.assert_called_once_with(True)

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_device")
@pytest.mark.usefixtures("mock_zeroconf")
@pytest.mark.parametrize(
    "name, get_method, update_interval",
    [
        ["enable_guest_wifi", "async_get_wifi_guest_access", SHORT_UPDATE_INTERVAL],
        ["enable_leds", "async_get_led_setting", SHORT_UPDATE_INTERVAL],
    ],
)
async def test_device_failure(
    hass: HomeAssistant, name: str, get_method: str, update_interval: timedelta
):
    """Test device failure."""
    state_key = f"{DOMAIN}.{name}"
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None

    with patch(
        f"devolo_plc_api.device_api.deviceapi.DeviceApi.{get_method}",
        side_effect=DeviceUnavailable,
    ):
        async_fire_time_changed(hass, dt.utcnow() + update_interval)
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
