"""Tests for the Risco event sensors."""
import pytest

from homeassistant.components.risco import (
    LAST_EVENT_TIMESTAMP_KEY,
    CannotConnectError,
    UnauthorizedError,
)
from homeassistant.components.risco.const import DOMAIN, EVENTS_COORDINATOR

from .util import TEST_CONFIG, setup_risco

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry

ENTITY_IDS = {
    "Alarm": "sensor.risco_test_site_name_alarm_events",
    "Status": "sensor.risco_test_site_name_status_events",
    "Trouble": "sensor.risco_test_site_name_trouble_events",
    "Other": "sensor.risco_test_site_name_other_events",
}

TEST_EVENTS = [
    MagicMock(
        time="2020-09-02T10:00:00Z",
        category_id=4,
        category_name="System Status",
        type_id=16,
        type_name="disarmed",
        name="'user' disarmed 'partition'",
        text="",
        partition_id=0,
        zone_id=None,
        user_id=3,
        group=None,
        priority=2,
        raw={},
    ),
    MagicMock(
        time="2020-09-02T09:00:00Z",
        category_id=7,
        category_name="Troubles",
        type_id=36,
        type_name="service needed",
        name="Device Fault",
        text="Service is needed.",
        partition_id=None,
        zone_id=None,
        user_id=None,
        group=None,
        priority=1,
        raw={},
    ),
    MagicMock(
        time="2020-09-02T08:00:00Z",
        category_id=2,
        category_name="Alarms",
        type_id=3,
        type_name="triggered",
        name="Alarm is on",
        text="Yes it is.",
        partition_id=0,
        zone_id=12,
        user_id=None,
        group=None,
        priority=0,
        raw={},
    ),
    MagicMock(
        time="2020-09-02T07:00:00Z",
        category_id=4,
        category_name="System Status",
        type_id=119,
        type_name="group arm",
        name="You armed a group",
        text="",
        partition_id=0,
        zone_id=None,
        user_id=1,
        group="C",
        priority=2,
        raw={},
    ),
    MagicMock(
        time="2020-09-02T06:00:00Z",
        category_id=8,
        category_name="Made up",
        type_id=200,
        type_name="also made up",
        name="really made up",
        text="",
        partition_id=2,
        zone_id=None,
        user_id=1,
        group=None,
        priority=2,
        raw={},
    ),
]

CATEGORIES_TO_EVENTS = {
    "Alarm": 2,
    "Status": 0,
    "Trouble": 1,
    "Other": 4,
}


@pytest.fixture
def emptry_alarm():
    """Fixture to mock an empty alarm."""
    with patch(
        "homeassistant.components.risco.RiscoAPI.get_state",
        return_value=MagicMock(paritions={}, zones={}),
    ):
        yield


async def test_cannot_connect(hass):
    """Test connection error."""

    with patch(
        "homeassistant.components.risco.RiscoAPI.login",
        side_effect=CannotConnectError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    registry = await hass.helpers.entity_registry.async_get_registry()
    for id in ENTITY_IDS.values():
        assert not registry.async_is_registered(id)


async def test_unauthorized(hass):
    """Test unauthorized error."""

    with patch(
        "homeassistant.components.risco.RiscoAPI.login",
        side_effect=UnauthorizedError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    registry = await hass.helpers.entity_registry.async_get_registry()
    for id in ENTITY_IDS.values():
        assert not registry.async_is_registered(id)


def _check_state(hass, category, entity_id):
    event = TEST_EVENTS[CATEGORIES_TO_EVENTS[category]]
    assert hass.states.get(entity_id).state == event.time
    assert hass.states.get(entity_id).attributes["category_id"] == event.category_id
    assert hass.states.get(entity_id).attributes["category_name"] == event.category_name
    assert hass.states.get(entity_id).attributes["type_id"] == event.type_id
    assert hass.states.get(entity_id).attributes["type_name"] == event.type_name
    assert hass.states.get(entity_id).attributes["name"] == event.name
    assert hass.states.get(entity_id).attributes["text"] == event.text
    assert hass.states.get(entity_id).attributes["partition_id"] == event.partition_id
    assert hass.states.get(entity_id).attributes["zone_id"] == event.zone_id
    assert hass.states.get(entity_id).attributes["user_id"] == event.user_id
    assert hass.states.get(entity_id).attributes["group"] == event.group
    assert hass.states.get(entity_id).attributes["priority"] == event.priority
    assert hass.states.get(entity_id).attributes["raw"] == event.raw


async def test_setup(hass, emptry_alarm):
    """Test entity setup."""
    registry = await hass.helpers.entity_registry.async_get_registry()

    for id in ENTITY_IDS.values():
        assert not registry.async_is_registered(id)

    with patch(
        "homeassistant.components.risco.RiscoAPI.get_events",
        return_value=TEST_EVENTS,
    ), patch(
        "homeassistant.components.risco.Store.async_save",
    ) as save_mock:
        entry = await setup_risco(hass)
        await hass.async_block_till_done()
        save_mock.assert_awaited_once_with(
            {LAST_EVENT_TIMESTAMP_KEY: TEST_EVENTS[0].time}
        )

    for id in ENTITY_IDS.values():
        assert registry.async_is_registered(id)

    for category, entity_id in ENTITY_IDS.items():
        _check_state(hass, category, entity_id)

    coordinator = hass.data[DOMAIN][entry.entry_id][EVENTS_COORDINATOR]
    with patch(
        "homeassistant.components.risco.RiscoAPI.get_events", return_value=[]
    ) as events_mock, patch(
        "homeassistant.components.risco.Store.async_load",
        return_value={LAST_EVENT_TIMESTAMP_KEY: TEST_EVENTS[0].time},
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        events_mock.assert_awaited_once_with(TEST_EVENTS[0].time, 10)

    for category, entity_id in ENTITY_IDS.items():
        _check_state(hass, category, entity_id)
