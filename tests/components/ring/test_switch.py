"""The tests for the Ring switch platform."""

from unittest.mock import Mock

import pytest
import ring_doorbell
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.ring.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .common import MockConfigEntry, setup_automation, setup_platform
from .device_mocks import FRONT_DOOR_DEVICE_ID

from tests.common import snapshot_platform


@pytest.fixture
def create_deprecated_siren_entity(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
):
    """Create the entity so it is not ignored by the deprecation check."""
    mock_config_entry.add_to_hass(hass)

    def create_entry(device_name, device_id):
        unique_id = f"{device_id}-siren"

        entity_registry.async_get_or_create(
            domain=SWITCH_DOMAIN,
            platform=DOMAIN,
            unique_id=unique_id,
            suggested_object_id=f"{device_name}_siren",
            config_entry=mock_config_entry,
        )

    create_entry("front", 765432)
    create_entry("internal", 345678)


async def test_states(
    hass: HomeAssistant,
    mock_ring_client: Mock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    create_deprecated_siren_entity,
) -> None:
    """Test states."""

    mock_config_entry.add_to_hass(hass)
    await setup_platform(hass, Platform.SWITCH)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_siren_off_reports_correctly(
    hass: HomeAssistant, mock_ring_client, create_deprecated_siren_entity
) -> None:
    """Tests that the initial state of a device that should be off is correct."""
    await setup_platform(hass, Platform.SWITCH)

    state = hass.states.get("switch.front_siren")
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Front Siren"


async def test_siren_on_reports_correctly(
    hass: HomeAssistant, mock_ring_client, create_deprecated_siren_entity
) -> None:
    """Tests that the initial state of a device that should be on is correct."""
    await setup_platform(hass, Platform.SWITCH)

    state = hass.states.get("switch.internal_siren")
    assert state.state == "on"
    assert state.attributes.get("friendly_name") == "Internal Siren"


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("switch.front_siren"),
        ("switch.front_door_in_home_chime"),
        ("switch.front_motion_detection"),
    ],
)
async def test_switch_can_be_turned_on_and_off(
    hass: HomeAssistant,
    mock_ring_client,
    create_deprecated_siren_entity,
    entity_id,
) -> None:
    """Tests the switch turns on and off correctly."""
    await setup_platform(hass, Platform.SWITCH)

    assert hass.states.get(entity_id)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("exception_type", "reauth_expected"),
    [
        (ring_doorbell.AuthenticationError, True),
        (ring_doorbell.RingTimeout, False),
        (ring_doorbell.RingError, False),
    ],
    ids=["Authentication", "Timeout", "Other"],
)
async def test_switch_errors_when_turned_on(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    exception_type,
    reauth_expected,
    create_deprecated_siren_entity,
) -> None:
    """Tests the switch turns on correctly."""
    await setup_platform(hass, Platform.SWITCH)
    config_entry = hass.config_entries.async_entries("ring")[0]

    assert not any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))

    front_siren_mock = mock_ring_devices.get_device(765432)
    front_siren_mock.async_set_siren.side_effect = exception_type

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.front_siren"}, blocking=True
        )
    await hass.async_block_till_done()
    front_siren_mock.async_set_siren.assert_called_once()
    assert (
        any(
            flow
            for flow in config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
            if flow["handler"] == "ring"
        )
        == reauth_expected
    )


async def test_switch_dynamic_exists(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ring_client: Mock,
    mock_ring_devices: Mock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Tests the switch turns on and off correctly."""

    mock_config_entry.add_to_hass(hass)
    entity_id = "switch.front_door_in_home_chime"
    issue_id = f"dynamic_entity_{entity_id}_automation.test_automation"

    # Create the switch as it's present
    front_door_mock = mock_ring_devices.get_device(FRONT_DOOR_DEVICE_ID)
    front_door_mock.configure_mock(existing_doorbell_type="Mechanical")
    await setup_platform(hass, Platform.SWITCH)

    entry = entity_registry.async_get(entity_id)
    assert entry
    state = hass.states.get(entity_id)
    assert state

    # Test being unavailable because of an automation
    await setup_automation(hass, "test_automation", entity_id)

    front_door_mock.configure_mock(existing_doorbell_type="Not Present")
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    state = hass.states.get(entity_id)
    assert state.state is STATE_UNAVAILABLE

    await hass.async_block_till_done()

    # Remove the automation and reload should remove the entity.
    await next(iter(hass.data[AUTOMATION_DOMAIN].entities)).async_remove()
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    entry = entity_registry.async_get(entity_id)
    assert entry is None
    state = hass.states.get(entity_id)
    assert state is None

    # Another reload should keep the same state
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    entry = entity_registry.async_get(entity_id)
    assert entry is None
    state = hass.states.get(entity_id)
    assert state is None
