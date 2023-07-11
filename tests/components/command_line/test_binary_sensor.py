"""The tests for the Command line Binary sensor platform."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import setup
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.command_line.binary_sensor import CommandBinarySensor
from homeassistant.components.command_line.const import DOMAIN
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.issue_registry as ir
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_setup_platform_yaml(hass: HomeAssistant) -> None:
    """Test sensor setup."""
    assert await setup.async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": "command_line",
                "name": "Test",
                "command": "echo 1",
                "payload_on": "1",
                "payload_off": "0",
            }
        },
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_ON
    assert entity_state.name == "Test"

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_binary_sensor")
    assert issue.translation_key == "deprecated_platform_yaml"


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "binary_sensor": {
                        "name": "Test",
                        "command": "echo 1",
                        "payload_on": "1",
                        "payload_off": "0",
                        "command_timeout": 15,
                    }
                }
            ]
        }
    ],
)
async def test_setup_integration_yaml(
    hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test sensor setup."""

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_ON
    assert entity_state.name == "Test"


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "binary_sensor": {
                        "name": "Test",
                        "command": "echo 10",
                        "payload_on": "1.0",
                        "payload_off": "0",
                        "value_template": "{{ value | multiply(0.1) }}",
                    }
                }
            ]
        }
    ],
)
async def test_template(hass: HomeAssistant, load_yaml_integration: None) -> None:
    """Test setting the state with a template."""

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_ON


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "binary_sensor": {
                        "name": "Test",
                        "command": "echo 0",
                        "payload_on": "1",
                        "payload_off": "0",
                    }
                }
            ]
        }
    ],
)
async def test_sensor_off(hass: HomeAssistant, load_yaml_integration: None) -> None:
    """Test setting the state with a template."""

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_OFF


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "binary_sensor": {
                        "unique_id": "unique",
                        "command": "echo 0",
                    }
                },
                {
                    "binary_sensor": {
                        "unique_id": "not-so-unique-anymore",
                        "command": "echo 1",
                    }
                },
                {
                    "binary_sensor": {
                        "unique_id": "not-so-unique-anymore",
                        "command": "echo 2",
                    }
                },
            ]
        }
    ],
)
async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, load_yaml_integration: None
) -> None:
    """Test unique_id option and if it only creates one binary sensor per id."""

    assert len(hass.states.async_all()) == 2

    assert len(entity_registry.entities) == 2
    assert entity_registry.async_get_entity_id(
        "binary_sensor", "command_line", "unique"
    )
    assert entity_registry.async_get_entity_id(
        "binary_sensor", "command_line", "not-so-unique-anymore"
    )


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "binary_sensor": {
                        "command": "exit 33",
                    }
                }
            ]
        }
    ],
)
async def test_return_code(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, get_config: dict[str, Any]
) -> None:
    """Test setting the state with a template."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        get_config,
    )
    await hass.async_block_till_done()
    assert "return code 33" in caplog.text


async def test_updating_to_often(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling updating when command already running."""
    called = []

    class MockCommandBinarySensor(CommandBinarySensor):
        """Mock entity that updates slow."""

        async def _async_update(self) -> None:
            """Update slow."""
            called.append(1)
            # Add waiting time
            await asyncio.sleep(1)

    with patch(
        "homeassistant.components.command_line.binary_sensor.CommandBinarySensor",
        side_effect=MockCommandBinarySensor,
    ):
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "binary_sensor": {
                            "name": "Test",
                            "command": "echo 1",
                            "payload_on": "1",
                            "payload_off": "0",
                            "scan_interval": 0.1,
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

    assert called
    assert (
        "Updating Command Line Binary Sensor Test took longer than the scheduled update interval"
        not in caplog.text
    )
    called.clear()
    caplog.clear()

    async_fire_time_changed(hass, dt_util.now() + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert called
    assert (
        "Updating Command Line Binary Sensor Test took longer than the scheduled update interval"
        in caplog.text
    )

    await asyncio.sleep(0.2)


async def test_updating_manually(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling manual updating using homeassistant udate_entity service."""
    await setup.async_setup_component(hass, HA_DOMAIN, {})
    called = []

    class MockCommandBinarySensor(CommandBinarySensor):
        """Mock entity that updates slow."""

        async def _async_update(self) -> None:
            """Update slow."""
            called.append(1)
            # Add waiting time
            await asyncio.sleep(1)

    with patch(
        "homeassistant.components.command_line.binary_sensor.CommandBinarySensor",
        side_effect=MockCommandBinarySensor,
    ):
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "binary_sensor": {
                            "name": "Test",
                            "command": "echo 1",
                            "payload_on": "1",
                            "payload_off": "0",
                            "scan_interval": 10,
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

    assert len(called) == 1

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["binary_sensor.test"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(called) == 2

    await asyncio.sleep(0.2)
