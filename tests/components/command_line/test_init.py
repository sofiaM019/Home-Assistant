"""Test Command line component setup process."""
from __future__ import annotations

from datetime import timedelta

import pytest

from homeassistant.components.command_line.const import DOMAIN
from homeassistant.const import SERVICE_RELOAD, STATE_ON, STATE_OPEN
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


async def test_setup_config(hass: HomeAssistant, load_yaml_integration: None) -> None:
    """Test setup from yaml."""

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    state_binary_sensor = hass.states.get("binary_sensor.test")
    state_sensor = hass.states.get("sensor.test")
    state_cover = hass.states.get("cover.test")
    state_switch = hass.states.get("switch.test")

    assert state_binary_sensor.state == STATE_ON
    assert state_sensor.state == "5"
    assert state_cover.state == STATE_OPEN
    assert state_switch.state == STATE_ON


async def test_reload_service(
    hass: HomeAssistant, load_yaml_integration: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reload serviice."""

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    state_binary_sensor = hass.states.get("binary_sensor.test")
    assert state_binary_sensor.state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        SERVICE_RELOAD,
        {},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert "Loading platforms from reload" in caplog.text

    state_binary_sensor = hass.states.get("binary_sensor.test")
    assert state_binary_sensor.state == STATE_ON
