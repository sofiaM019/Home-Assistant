"""Test the Switch config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.group import DOMAIN, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    (
        "group_type",
        "group_state",
        "member_state",
        "member_attributes",
        "extra_input",
        "extra_options",
        "extra_attrs",
    ),
    (
        ("binary_sensor", "on", "on", {}, {}, {"all": False}, {}),
        ("binary_sensor", "on", "on", {}, {"all": True}, {"all": True}, {}),
        ("cover", "open", "open", {}, {}, {}, {}),
        ("fan", "on", "on", {}, {}, {}, {}),
        ("light", "on", "on", {}, {}, {}, {}),
        ("lock", "locked", "locked", {}, {}, {}, {}),
        ("media_player", "on", "on", {}, {}, {}, {}),
        (
            "sensor",
            "20.0",
            "10",
            {},
            {"type": "sum"},
            {"type": "sum"},
            {},
        ),
        ("switch", "on", "on", {}, {}, {}, {}),
    ),
)
async def test_config_flow(
    hass: HomeAssistant,
    group_type,
    group_state,
    member_state,
    member_attributes,
    extra_input,
    extra_options,
    extra_attrs,
) -> None:
    """Test the config flow."""
    members = [f"{group_type}.one", f"{group_type}.two"]
    for member in members:
        hass.states.async_set(member, member_state, member_attributes)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": group_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == group_type

    with patch(
        "homeassistant.components.group.async_setup_entry", wraps=async_setup_entry
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Living Room",
                "entities": members,
                **extra_input,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room"
    assert result["data"] == {}
    assert result["options"] == {
        "entities": members,
        "group_type": group_type,
        "hide_members": False,
        "name": "Living Room",
        **extra_options,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "entities": members,
        "group_type": group_type,
        "hide_members": False,
        "name": "Living Room",
        **extra_options,
    }

    state = hass.states.get(f"{group_type}.living_room")
    assert state.state == group_state
    assert state.attributes["entity_id"] == members
    for key in extra_attrs:
        assert state.attributes[key] == extra_attrs[key]


@pytest.mark.parametrize(
    ("hide_members", "hidden_by"), ((False, None), (True, "integration"))
)
@pytest.mark.parametrize(
    ("group_type", "extra_input"),
    (
        ("binary_sensor", {"all": False}),
        ("cover", {}),
        ("fan", {}),
        ("light", {}),
        ("lock", {}),
        ("media_player", {}),
        ("switch", {}),
    ),
)
async def test_config_flow_hides_members(
    hass: HomeAssistant, group_type, extra_input, hide_members, hidden_by
) -> None:
    """Test the config flow hides members if requested."""
    fake_uuid = "a266a680b608c32770e6c45bfe6b8411"
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        group_type, "test", "unique", suggested_object_id="one"
    )
    assert entry.entity_id == f"{group_type}.one"
    assert entry.hidden_by is None

    entry = registry.async_get_or_create(
        group_type, "test", "unique3", suggested_object_id="three"
    )
    assert entry.entity_id == f"{group_type}.three"
    assert entry.hidden_by is None

    members = [f"{group_type}.one", f"{group_type}.two", fake_uuid, entry.id]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": group_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == group_type

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Living Room",
            "entities": members,
            "hide_members": hide_members,
            **extra_input,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY

    assert registry.async_get(f"{group_type}.one").hidden_by == hidden_by
    assert registry.async_get(f"{group_type}.three").hidden_by == hidden_by


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema:
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize(
    ("group_type", "member_state", "extra_options", "options_options"),
    (
        ("binary_sensor", "on", {"all": False}, {}),
        ("cover", "open", {}, {}),
        ("fan", "on", {}, {}),
        ("light", "on", {"all": False}, {}),
        ("lock", "locked", {}, {}),
        ("media_player", "on", {}, {}),
        (
            "sensor",
            "10",
            {"ignore_non_numeric": False, "type": "sum"},
            {"ignore_non_numeric": False, "type": "sum"},
        ),
        ("switch", "on", {"all": False}, {}),
    ),
)
async def test_options(
    hass: HomeAssistant, group_type, member_state, extra_options, options_options
) -> None:
    """Test reconfiguring."""
    members1 = [f"{group_type}.one", f"{group_type}.two"]
    members2 = [f"{group_type}.four", f"{group_type}.five"]

    for member in members1:
        hass.states.async_set(member, member_state, {})
    for member in members2:
        hass.states.async_set(member, member_state, {})

    group_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entities": members1,
            "group_type": group_type,
            "name": "Bed Room",
            **extra_options,
        },
        title="Bed Room",
    )
    group_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(group_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{group_type}.bed_room")
    assert state.attributes["entity_id"] == members1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == group_type
    assert get_suggested(result["data_schema"].schema, "entities") == members1
    assert "name" not in result["data_schema"].schema
    assert result["data_schema"].schema["entities"].config["exclude_entities"] == [
        f"{group_type}.bed_room"
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"entities": members2, **options_options},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "entities": members2,
        "group_type": group_type,
        "hide_members": False,
        "name": "Bed Room",
        **extra_options,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "entities": members2,
        "group_type": group_type,
        "hide_members": False,
        "name": "Bed Room",
        **extra_options,
    }
    assert config_entry.title == "Bed Room"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()
    state = hass.states.get(f"{group_type}.bed_room")
    assert state.attributes["entity_id"] == members2

    # Check we don't get suggestions from another entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": group_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == group_type

    assert get_suggested(result["data_schema"].schema, "entities") is None
    assert get_suggested(result["data_schema"].schema, "name") is None


@pytest.mark.parametrize(
    ("group_type", "extra_options", "extra_options_after", "advanced"),
    (
        ("light", {"all": False}, {"all": False}, False),
        ("light", {"all": True}, {"all": True}, False),
        ("light", {"all": False}, {"all": False}, True),
        ("light", {"all": True}, {"all": False}, True),
        ("switch", {"all": False}, {"all": False}, False),
        ("switch", {"all": True}, {"all": True}, False),
        ("switch", {"all": False}, {"all": False}, True),
        ("switch", {"all": True}, {"all": False}, True),
    ),
)
async def test_all_options(
    hass: HomeAssistant, group_type, extra_options, extra_options_after, advanced
) -> None:
    """Test reconfiguring."""
    members1 = [f"{group_type}.one", f"{group_type}.two"]
    members2 = [f"{group_type}.four", f"{group_type}.five"]

    group_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entities": members1,
            "group_type": group_type,
            "name": "Bed Room",
            **extra_options,
        },
        title="Bed Room",
    )
    group_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(group_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{group_type}.bed_room")

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": advanced}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == group_type

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": members2,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "entities": members2,
        "group_type": group_type,
        "hide_members": False,
        "name": "Bed Room",
        **extra_options_after,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "entities": members2,
        "group_type": group_type,
        "hide_members": False,
        "name": "Bed Room",
        **extra_options_after,
    }
    assert config_entry.title == "Bed Room"


@pytest.mark.parametrize(
    ("hide_members", "hidden_by_initial", "hidden_by"),
    (
        (False, er.RegistryEntryHider.INTEGRATION, None),
        (True, None, er.RegistryEntryHider.INTEGRATION),
    ),
)
@pytest.mark.parametrize(
    ("group_type", "extra_input"),
    (
        ("binary_sensor", {"all": False}),
        ("cover", {}),
        ("fan", {}),
        ("light", {}),
        ("lock", {}),
        ("media_player", {}),
        ("switch", {}),
    ),
)
async def test_options_flow_hides_members(
    hass: HomeAssistant,
    group_type,
    extra_input,
    hide_members,
    hidden_by_initial,
    hidden_by,
) -> None:
    """Test the options flow hides or unhides members if requested."""
    fake_uuid = "a266a680b608c32770e6c45bfe6b8411"
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        group_type,
        "test",
        "unique1",
        suggested_object_id="one",
        hidden_by=hidden_by_initial,
    )
    assert entry.entity_id == f"{group_type}.one"

    entry = registry.async_get_or_create(
        group_type,
        "test",
        "unique3",
        suggested_object_id="three",
        hidden_by=hidden_by_initial,
    )
    assert entry.entity_id == f"{group_type}.three"

    members = [f"{group_type}.one", f"{group_type}.two", fake_uuid, entry.id]

    group_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entities": members,
            "group_type": group_type,
            "hide_members": False,
            "name": "Bed Room",
            **extra_input,
        },
        title="Bed Room",
    )
    group_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(group_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(group_config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": members,
            "hide_members": hide_members,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY

    assert registry.async_get(f"{group_type}.one").hidden_by == hidden_by
    assert registry.async_get(f"{group_type}.three").hidden_by == hidden_by


async def test_config_flow_sensor_preview(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "sensor"},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "sensor"
    assert result["errors"] is None
    assert result["preview"] == "group_sensor"

    await client.send_json_auto_id(
        {
            "type": "group/sensor/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {
                "name": "My sensor group",
                "entities": input_sensors,
                "type": "max",
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {
            "friendly_name": "My sensor group",
            "icon": "mdi:calculator",
        },
        "state": "unavailable",
    }

    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {
            "entity_id": ["sensor.input_one", "sensor.input_two"],
            "friendly_name": "My sensor group",
            "icon": "mdi:calculator",
            "max_entity_id": "sensor.input_two",
        },
        "state": "20.0",
    }


async def test_option_flow_sensor_preview(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the option flow preview."""
    client = await hass_ws_client(hass)

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entities": ["sensor.input_one", "sensor.input_two"],
            "group_type": "sensor",
            "hide_members": False,
            "name": "My sensor group",
            "type": "min",
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "group_sensor"

    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    await client.send_json_auto_id(
        {
            "type": "group/sensor/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {
                "entities": input_sensors,
                "type": "min",
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {
            "entity_id": ["sensor.input_one", "sensor.input_two"],
            "friendly_name": "My sensor group",
            "icon": "mdi:calculator",
            "min_entity_id": "sensor.input_one",
        },
        "state": "10.0",
    }


async def test_option_flow_sensor_preview_config_entry_removed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the option flow preview where the config entry is removed."""
    client = await hass_ws_client(hass)

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entities": ["sensor.input_one", "sensor.input_two"],
            "group_type": "sensor",
            "hide_members": False,
            "name": "My sensor group",
            "type": "min",
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "group_sensor"

    await hass.config_entries.async_remove(config_entry.entry_id)

    await client.send_json_auto_id(
        {
            "type": "group/sensor/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {
                "entities": input_sensors,
                "type": "min",
            },
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {"code": "unknown_error", "message": "Unknown error"}
