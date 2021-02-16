"""The tests the cover command line platform."""
import os
import tempfile
from unittest.mock import patch

from homeassistant import config as hass_config, setup
from homeassistant.components.cover import DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_RELOAD,
    SERVICE_STOP_COVER,
)
from homeassistant.helpers.typing import Any, Dict, HomeAssistantType
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


async def setup_test_entity(
    hass: HomeAssistantType, config_dict: Dict[str, Any]
) -> None:
    """Set up a test command line notify service."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {"platform": "command_line", "covers": {"test": config_dict}},
            ]
        },
    )
    await hass.async_block_till_done()


async def test_no_poll_when_cover_has_no_command_state(hass: HomeAssistantType) -> None:
    """Test that the cover does not polls when there's no state command."""

    with patch(
        "homeassistant.components.command_line.subprocess.check_output",
        return_value=b"50\n",
    ) as check_output:
        await setup_test_entity(hass, {})
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        assert not check_output.called


async def test_poll_when_cover_has_command_state(hass: HomeAssistantType) -> None:
    """Test that the cover polls when there's a state  command."""

    with patch(
        "homeassistant.components.command_line.subprocess.check_output",
        return_value=b"50\n",
    ) as check_output:
        await setup_test_entity(hass, {"command_state": "echo state"})
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        check_output.assert_called_once_with(
            "echo state", shell=True, timeout=15  # nosec # shell by design
        )


async def test_state_value(hass: HomeAssistantType) -> None:
    """Test with state value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "cover_status")
        await setup_test_entity(
            hass,
            {
                "command_state": f"cat {path}",
                "command_open": f"echo 1 > {path}",
                "command_close": f"echo 1 > {path}",
                "command_stop": f"echo 0 > {path}",
                "value_template": "{{ value }}",
            },
        )

        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "unknown"

        await hass.services.async_call(
            DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
        )
        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "open"

        await hass.services.async_call(
            DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
        )
        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "open"

        await hass.services.async_call(
            DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
        )
        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "closed"


async def test_reload(hass: HomeAssistantType) -> None:
    """Verify we can reload command_line covers."""

    await setup_test_entity(
        hass,
        {
            "command_state": "echo open",
            "value_template": "{{ value }}",
        },
    )
    entity_state = hass.states.get("cover.test")
    assert entity_state
    assert entity_state.state == "unknown"

    yaml_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "fixtures",
        "command_line/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            "command_line",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert not hass.states.get("cover.test")
    assert hass.states.get("cover.from_yaml")
