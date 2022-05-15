"""The tests for the Command line switch platform."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from unittest.mock import patch

from pytest import LogCaptureFixture

from homeassistant import setup
from homeassistant.components.command_line.const import (
    CONF_COMMAND_TIMEOUT,
    CONF_OBJECT_ID,
)
from homeassistant.components.switch import DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.util.dt as dt_util

from . import setup_test_entity

from tests.common import async_fire_time_changed


async def test_state_none(hass: HomeAssistant) -> None:
    """Test with none state."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        assert await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: [
                    {
                        "platform": "command_line",
                        "switches": {
                            "test": {
                                "command_on": f"echo 1 > {path}",
                                "command_off": f"echo 0 > {path}",
                            }
                        },
                    },
                ]
            },
        )
        await hass.async_block_till_done()

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF


async def test_state_value(hass: HomeAssistant) -> None:
    """Test with state value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        assert await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: [
                    {
                        "platform": "command_line",
                        "switches": {
                            "test": {
                                "command_state": f"cat {path}",
                                "command_on": f"echo 1 > {path}",
                                "command_off": f"echo 0 > {path}",
                                "value_template": '{{ value=="1" }}',
                                "icon_template": '{% if value=="1" %} mdi:on {% else %} mdi:off {% endif %}',
                            }
                        },
                    },
                ]
            },
        )
        await hass.async_block_till_done()

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON
        assert entity_state.attributes.get("icon") == "mdi:on"

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF
        assert entity_state.attributes.get("icon") == "mdi:off"


async def test_state_json_value(hass: HomeAssistant) -> None:
    """Test with state JSON value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        oncmd = json.dumps({"status": "ok"})
        offcmd = json.dumps({"status": "nope"})

        await setup_test_entity(
            hass,
            {
                CONF_OBJECT_ID: "test",
                CONF_PLATFORM: "switch",
                CONF_NAME: "Test",
                CONF_COMMAND_TIMEOUT: 15,
                "command_state": f"cat {path}",
                "command_on": f"echo '{oncmd}' > {path}",
                "command_off": f"echo '{offcmd}' > {path}",
                "value_template": '{{ value_json.status=="ok" }}',
                "icon_template": '{% if value_json.status=="ok" %} mdi:on {% else %} mdi:off {% endif %}',
            },
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON
        assert entity_state.attributes.get("icon") == "mdi:on"

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF
        assert entity_state.attributes.get("icon") == "mdi:off"


async def test_state_code(hass: HomeAssistant) -> None:
    """Test with state code."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        await setup_test_entity(
            hass,
            {
                CONF_OBJECT_ID: "test",
                CONF_PLATFORM: "switch",
                CONF_NAME: "Test",
                CONF_COMMAND_TIMEOUT: 15,
                "command_state": f"cat {path}",
                "command_on": f"echo 1 > {path}",
                "command_off": f"echo 0 > {path}",
            },
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON


async def test_assumed_state_should_be_true_if_command_state_is_none(
    hass: HomeAssistant,
) -> None:
    """Test with state value."""

    await setup_test_entity(
        hass,
        {
            CONF_OBJECT_ID: "test",
            CONF_PLATFORM: "switch",
            CONF_NAME: "Test",
            CONF_COMMAND_TIMEOUT: 15,
            "command_on": "echo 'on command'",
            "command_off": "echo 'off command'",
        },
    )
    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.attributes["assumed_state"]


async def test_assumed_state_should_absent_if_command_state_present(
    hass: HomeAssistant,
) -> None:
    """Test with state value."""

    await setup_test_entity(
        hass,
        {
            CONF_OBJECT_ID: "test",
            CONF_PLATFORM: "switch",
            CONF_NAME: "Test",
            CONF_COMMAND_TIMEOUT: 15,
            "command_on": "echo 'on command'",
            "command_off": "echo 'off command'",
            "command_state": "cat {}",
        },
    )
    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert "assumed_state" not in entity_state.attributes


async def test_name_is_set_correctly(hass: HomeAssistant) -> None:
    """Test that name is set correctly."""
    await setup_test_entity(
        hass,
        {
            CONF_OBJECT_ID: "test",
            CONF_PLATFORM: "switch",
            CONF_NAME: "Test",
            CONF_COMMAND_TIMEOUT: 15,
            "command_on": "echo 'on command'",
            "command_off": "echo 'off command'",
            "friendly_name": "Test friendly name!",
        },
    )

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.name == "Test friendly name!"


async def test_switch_command_state_fail(
    caplog: LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test that switch failures are handled correctly."""
    await setup_test_entity(
        hass,
        {
            CONF_OBJECT_ID: "test",
            CONF_PLATFORM: "switch",
            CONF_NAME: "Test",
            CONF_COMMAND_TIMEOUT: 15,
            "command_on": "exit 0",
            "command_off": "exit 0'",
            "command_state": "echo 1",
        },
    )

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == "on"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == "on"

    assert "Command failed" in caplog.text


async def test_switch_command_state_code_exceptions(
    caplog: LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test that switch state code exceptions are handled correctly."""

    with patch(
        "homeassistant.components.command_line.util.subprocess.check_output",
        side_effect=[
            subprocess.TimeoutExpired("cmd", 10),
            subprocess.SubprocessError(),
        ],
    ) as check_output:
        await setup_test_entity(
            hass,
            {
                CONF_OBJECT_ID: "test",
                CONF_PLATFORM: "switch",
                CONF_NAME: "Test",
                CONF_COMMAND_TIMEOUT: 15,
                "command_on": "exit 0",
                "command_off": "exit 0'",
                "command_state": "echo 1",
            },
        )
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        assert check_output.called
        assert "Timeout for command" in caplog.text

        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL * 2)
        await hass.async_block_till_done()
        assert check_output.called
        assert "Error trying to exec command" in caplog.text


async def test_switch_command_state_value_exceptions(
    caplog: LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test that switch state value exceptions are handled correctly."""

    with patch(
        "homeassistant.components.command_line.util.subprocess.check_output",
        side_effect=[
            subprocess.TimeoutExpired("cmd", 10),
            subprocess.SubprocessError(),
        ],
    ) as check_output:
        await setup_test_entity(
            hass,
            {
                CONF_OBJECT_ID: "test",
                CONF_PLATFORM: "switch",
                CONF_NAME: "Test",
                CONF_COMMAND_TIMEOUT: 15,
                "command_on": "exit 0",
                "command_off": "exit 0'",
                "command_state": "echo 1",
                "value_template": '{{ value=="1" }}',
            },
        )
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        assert check_output.call_count == 1
        assert "Timeout for command" in caplog.text

        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL * 2)
        await hass.async_block_till_done()
        assert check_output.call_count == 2
        assert "Error trying to exec command" in caplog.text


async def test_no_switches(caplog: LogCaptureFixture, hass: HomeAssistant) -> None:
    """Test with no switches."""

    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "platform": "command_line",
                    "switches": {},
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert "No switches to import" in caplog.text


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id option and if it only creates one switch per id."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "platform": "command_line",
                    "switches": {
                        "unique": {
                            "command_on": "echo on",
                            "command_off": "echo off",
                            "unique_id": "unique",
                        },
                        "not_unique_1": {
                            "command_on": "echo on",
                            "command_off": "echo off",
                            "unique_id": "not-so-unique-anymore",
                        },
                        "not_unique_2": {
                            "command_on": "echo on",
                            "command_off": "echo off",
                            "unique_id": "not-so-unique-anymore",
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    ent_reg = entity_registry.async_get(hass)

    assert len(ent_reg.entities) == 2
    assert ent_reg.async_get_entity_id("switch", "command_line", "unique") is not None
    assert (
        ent_reg.async_get_entity_id("switch", "command_line", "not-so-unique-anymore")
        is not None
    )


async def test_command_failure(caplog: LogCaptureFixture, hass: HomeAssistant) -> None:
    """Test command failure."""

    await setup_test_entity(
        hass,
        {"test": {"command_off": "exit 33"}},
    )
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "switch.test"}, blocking=True
    )
    assert "return code 33" in caplog.text
