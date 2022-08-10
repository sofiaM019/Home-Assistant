"""Test for the Schedule integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from datetime import time
from typing import Any
from unittest.mock import patch

from aiohttp import ClientWebSocketResponse
from freezegun import freeze_time
import pytest

from homeassistant.components.schedule import STORAGE_VERSION, STORAGE_VERSION_MINOR
from homeassistant.components.schedule.const import (
    ATTR_FRIDAY,
    ATTR_FROM,
    ATTR_MONDAY,
    ATTR_NEXT_EVENT,
    ATTR_SATURDAY,
    ATTR_SUNDAY,
    ATTR_THURSDAY,
    ATTR_TO,
    ATTR_TUESDAY,
    ATTR_WEDNESDAY,
    CONF_FRIDAY,
    CONF_FROM,
    CONF_MONDAY,
    CONF_SATURDAY,
    CONF_SUNDAY,
    CONF_THURSDAY,
    CONF_TO,
    CONF_TUESDAY,
    CONF_WEDNESDAY,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_NAME,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockUser, async_fire_time_changed


@pytest.fixture
def schedule_setup(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> Callable[..., Coroutine[Any, Any, bool]]:
    """Schedule setup."""

    async def _schedule_setup(
        items: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> bool:
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": STORAGE_VERSION,
                "minor_version": STORAGE_VERSION_MINOR,
                "data": {
                    "items": [
                        {
                            CONF_ID: "from_storage",
                            CONF_NAME: "from storage",
                            CONF_ICON: "mdi:party-popper",
                            CONF_FRIDAY: [
                                {CONF_FROM: "17:00:00", CONF_TO: "23:59:59"},
                            ],
                            CONF_SATURDAY: [
                                {CONF_FROM: "00:00:00", CONF_TO: "23:59:59"},
                            ],
                            CONF_SUNDAY: [
                                {CONF_FROM: "00:00:00", CONF_TO: "23:59:59"},
                            ],
                        }
                    ]
                },
            }
        else:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "minor_version": STORAGE_VERSION_MINOR,
                "data": {"items": items},
            }
        if config is None:
            config = {
                DOMAIN: {
                    "from_yaml": {
                        CONF_NAME: "from yaml",
                        CONF_ICON: "mdi:party-pooper",
                        CONF_MONDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_TUESDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_WEDNESDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_THURSDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_FRIDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_SATURDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_SUNDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                    }
                }
            }
        return await async_setup_component(hass, DOMAIN, config)

    return _schedule_setup


async def test_invalid_config(hass: HomeAssistant) -> None:
    """Test invalid configs."""
    invalid_configs = [
        None,
        {},
        {"name with space": None},
    ]

    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_overlapping_time_ranges(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test overlapping time ranges invalidate."""
    assert not await schedule_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    CONF_NAME: "from yaml",
                    CONF_ICON: "mdi:party-pooper",
                    CONF_SUNDAY: [
                        {CONF_FROM: "00:00:00", CONF_TO: "23:59:59"},
                        {CONF_FROM: "07:00:00", CONF_TO: "08:00:00"},
                    ],
                }
            }
        }
    )
    assert "Overlapping times found in schedule" in caplog.text


async def test_setup_no_config(hass: HomeAssistant, hass_admin_user: MockUser) -> None:
    """Test component setup with no config."""
    count_start = len(hass.states.async_entity_ids())
    assert await async_setup_component(hass, DOMAIN, {})

    with patch(
        "homeassistant.config.load_yaml_config_file", autospec=True, return_value={}
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert count_start == len(hass.states.async_entity_ids())


@pytest.mark.freeze_time("2022-08-10 20:10:00-07:00")
async def test_load(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
) -> None:
    """Test set up from storage and YAML."""
    assert await schedule_setup()

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "from storage"
    assert state.attributes[ATTR_EDITABLE] is True
    assert state.attributes[ATTR_ICON] == "mdi:party-popper"
    assert state.attributes[ATTR_MONDAY] == []
    assert state.attributes[ATTR_TUESDAY] == []
    assert state.attributes[ATTR_WEDNESDAY] == []
    assert state.attributes[ATTR_THURSDAY] == []
    assert state.attributes[ATTR_FRIDAY] == [
        {ATTR_FROM: time(17, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_SATURDAY] == [
        {ATTR_FROM: time(00, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_SUNDAY] == [
        {ATTR_FROM: time(00, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-12T17:00:00-07:00"

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_FRIENDLY_NAME] == "from yaml"
    assert state.attributes[ATTR_EDITABLE] is False
    assert state.attributes[ATTR_ICON] == "mdi:party-pooper"
    assert state.attributes[ATTR_MONDAY] == [
        {ATTR_FROM: time(00, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_TUESDAY] == [
        {ATTR_FROM: time(00, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_WEDNESDAY] == [
        {ATTR_FROM: time(00, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_THURSDAY] == [
        {ATTR_FROM: time(00, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_FRIDAY] == [
        {ATTR_FROM: time(00, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_SATURDAY] == [
        {ATTR_FROM: time(00, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_SUNDAY] == [
        {ATTR_FROM: time(00, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-10T23:59:59-07:00"


async def test_schedule_updates(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
) -> None:
    """Test the schedule updates when time changes."""
    with freeze_time("2022-08-10 20:10:00-07:00"):
        assert await schedule_setup()

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-12T17:00:00-07:00"

    with freeze_time(state.attributes[ATTR_NEXT_EVENT]):
        async_fire_time_changed(hass, state.attributes[ATTR_NEXT_EVENT])
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-12T23:59:59-07:00"


async def test_ws_list(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
) -> None:
    """Test listing via WS."""
    assert await schedule_setup()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert result["from_storage"][ATTR_NAME] == "from storage"
    assert "from_yaml" not in result


async def test_ws_delete(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
) -> None:
    """Test WS delete cleans up entity registry."""
    ent_reg = er.async_get(hass)

    assert await schedule_setup()

    state = hass.states.get("schedule.from_storage")
    assert state is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "from_storage") is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/delete", f"{DOMAIN}_id": "from_storage"}
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get("schedule.from_storage")
    assert state is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "from_storage") is None


@pytest.mark.freeze_time("2022-08-10 20:10:00-07:00")
async def test_update(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
) -> None:
    """Test updating the schedule."""
    ent_reg = er.async_get(hass)

    assert await schedule_setup()

    state = hass.states.get("schedule.from_storage")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "from storage"
    assert state.attributes[ATTR_ICON] == "mdi:party-popper"
    assert state.attributes[ATTR_MONDAY] == []
    assert state.attributes[ATTR_TUESDAY] == []
    assert state.attributes[ATTR_WEDNESDAY] == []
    assert state.attributes[ATTR_THURSDAY] == []
    assert state.attributes[ATTR_FRIDAY] == [
        {ATTR_FROM: time(17, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_SATURDAY] == [
        {ATTR_FROM: time(00, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_SUNDAY] == [
        {ATTR_FROM: time(00, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-12T17:00:00-07:00"
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "from_storage") is not None

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": "from_storage",
            CONF_NAME: "Party pooper",
            CONF_ICON: "mdi:party-pooper",
            CONF_MONDAY: [],
            CONF_TUESDAY: [],
            CONF_WEDNESDAY: [{CONF_FROM: "17:00:00", CONF_TO: "23:59:59"}],
            CONF_THURSDAY: [],
            CONF_FRIDAY: [],
            CONF_SATURDAY: [],
            CONF_SUNDAY: [],
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get("schedule.from_storage")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Party pooper"
    assert state.attributes[ATTR_ICON] == "mdi:party-pooper"
    assert state.attributes[ATTR_MONDAY] == []
    assert state.attributes[ATTR_TUESDAY] == []
    assert state.attributes[ATTR_WEDNESDAY] == [
        {ATTR_FROM: time(17, 00, 00), ATTR_TO: time(23, 59, 59)}
    ]
    assert state.attributes[ATTR_THURSDAY] == []
    assert state.attributes[ATTR_FRIDAY] == []
    assert state.attributes[ATTR_SATURDAY] == []
    assert state.attributes[ATTR_SUNDAY] == []
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-10T23:59:59-07:00"


async def test_ws_create(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
) -> None:
    """Test create WS."""
    ent_reg = er.async_get(hass)

    assert await schedule_setup(items=[])

    state = hass.states.get("schedule.party_mode")
    assert state is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "party_mode") is None

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/create",
            "name": "Party mode",
            "icon": "mdi:party-popper",
            "monday": [{"from": "12:00:00", "to": "14:00:00"}],
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get("schedule.party_mode")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Party mode"
    assert state.attributes[ATTR_EDITABLE] is True
    assert state.attributes[ATTR_ICON] == "mdi:party-popper"
    assert state.attributes[ATTR_MONDAY] == [
        {ATTR_FROM: time(12, 00, 00), ATTR_TO: time(14, 00, 00)}
    ]
    assert state.attributes[ATTR_TUESDAY] == []
    assert state.attributes[ATTR_WEDNESDAY] == []
    assert state.attributes[ATTR_THURSDAY] == []
    assert state.attributes[ATTR_FRIDAY] == []
    assert state.attributes[ATTR_SATURDAY] == []
    assert state.attributes[ATTR_SUNDAY] == []
