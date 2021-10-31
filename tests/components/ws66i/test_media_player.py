"""The tests for WS66i Media player platform."""
from collections import defaultdict
from unittest.mock import patch

from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.components.ws66i.const import (
    CONF_NOT_FIRST_RUN,
    CONF_SOURCES,
    DOMAIN,
    SERVICE_RESTORE,
    SERVICE_SNAPSHOT,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry

MOCK_CONFIG = {CONF_IP_ADDRESS: "fake ip", CONF_SOURCES: {"1": "one", "3": "three"}}
MOCK_OPTIONS = {CONF_SOURCES: {"2": "two", "4": "four"}}

ZONE_1_ID = "media_player.zone_11"
ZONE_2_ID = "media_player.zone_12"
ZONE_7_ID = "media_player.zone_21"


class AttrDict(dict):
    """Helper class for mocking attributes."""

    def __setattr__(self, name, value):
        """Set attribute."""
        self[name] = value

    def __getattr__(self, item):
        """Get attribute."""
        return self[item]


class MockWs66i:
    """Mock for pyws66i object."""

    def __init__(self):
        """Init mock object."""
        self.zones = defaultdict(
            lambda: AttrDict(power=True, volume=0, mute=True, source=1)
        )

    def open(self):
        """Open socket. Do nothing."""
        pass

    def close(self):
        """Close socket. Do nothing."""
        pass

    def zone_status(self, zone_id):
        """Get zone status."""
        status = self.zones[zone_id]
        status.zone = zone_id
        return AttrDict(status)

    def set_source(self, zone_id, source_idx):
        """Set source for zone."""
        self.zones[zone_id].source = source_idx

    def set_power(self, zone_id, power):
        """Turn zone on/off."""
        self.zones[zone_id].power = power

    def set_mute(self, zone_id, mute):
        """Mute/unmute zone."""
        self.zones[zone_id].mute = mute

    def set_volume(self, zone_id, volume):
        """Set volume for zone."""
        self.zones[zone_id].volume = volume

    def restore_zone(self, zone):
        """Restore zone status."""
        self.zones[zone.zone] = AttrDict(zone)


async def test_cannot_connect(hass):
    """Test connection error."""

    patcher = patch("homeassistant.components.ws66i.get_ws66i", return_value=MockWs66i)
    ws66i = patcher.start()

    with patch.object(ws66i, "open", side_effect=ConnectionError):
        await async_update_entity(hass, ZONE_1_ID)
        await hass.async_block_till_done()
        assert hass.states.get(ZONE_1_ID) is None

    patcher.stop()


async def _setup_ws66i(hass, ws66i):
    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: ws66i,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def _setup_ws66i_with_options(hass, ws66i):
    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: ws66i,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_OPTIONS
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def _setup_ws66i_not_first_run(hass, ws66i):
    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: ws66i,
    ), patch(
        "homeassistant.components.ws66i.config_flow.get_ws66i",
        new=lambda *a: ws66i,
    ):
        data = {**MOCK_CONFIG, CONF_NOT_FIRST_RUN: True}
        config_entry = MockConfigEntry(domain=DOMAIN, data=data)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def _call_media_player_service(hass, name, data):
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, name, service_data=data, blocking=True
    )


async def _call_homeassistant_service(hass, name, data):
    await hass.services.async_call(
        "homeassistant", name, service_data=data, blocking=True
    )


async def _call_ws66i_service(hass, name, data):
    await hass.services.async_call(DOMAIN, name, service_data=data, blocking=True)


async def test_service_calls_with_entity_id(hass):
    """Test snapshot save/restore service calls."""
    await _setup_ws66i(hass, MockWs66i())

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    # Saving existing values
    await _call_ws66i_service(hass, SERVICE_SNAPSHOT, {"entity_id": ZONE_1_ID})

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "three"}
    )

    # Restoring other media player to its previous state
    # The zone should not be restored
    await _call_ws66i_service(hass, SERVICE_RESTORE, {"entity_id": ZONE_2_ID})
    await hass.async_block_till_done()

    # Checking that values were not (!) restored
    state = hass.states.get(ZONE_1_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "three"

    # Restoring media player to its previous state
    await _call_ws66i_service(hass, SERVICE_RESTORE, {"entity_id": ZONE_1_ID})
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "one"


async def test_service_calls_with_all_entities(hass):
    """Test snapshot save/restore service calls."""
    await _setup_ws66i(hass, MockWs66i())

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    # Saving existing values
    await _call_ws66i_service(hass, SERVICE_SNAPSHOT, {"entity_id": "all"})

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "three"}
    )

    # Restoring media player to its previous state
    await _call_ws66i_service(hass, SERVICE_RESTORE, {"entity_id": "all"})
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "one"


async def test_service_calls_without_relevant_entities(hass):
    """Test snapshot save/restore service calls."""
    await _setup_ws66i(hass, MockWs66i())

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    # Saving existing values
    await _call_ws66i_service(hass, SERVICE_SNAPSHOT, {"entity_id": "all"})

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "three"}
    )

    # Restoring media player to its previous state
    await _call_ws66i_service(hass, SERVICE_RESTORE, {"entity_id": "light.demo"})
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "three"


async def test_restore_without_snapshot(hass):
    """Test restore when snapshot wasn't called."""
    await _setup_ws66i(hass, MockWs66i())

    with patch.object(MockWs66i, "restore_zone") as method_call:
        await _call_ws66i_service(hass, SERVICE_RESTORE, {"entity_id": ZONE_1_ID})
        await hass.async_block_till_done()

        assert not method_call.called


async def test_update(hass):
    """Test updating values from ws66i."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    ws66i.set_source(11, 3)
    ws66i.set_volume(11, 38)

    await async_update_entity(hass, ZONE_1_ID)
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "three"


async def test_failed_update(hass):
    """Test updating failure from ws66i."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    ws66i.set_source(11, 3)
    ws66i.set_volume(11, 38)

    with patch.object(MockWs66i, "zone_status", return_value=None):
        await async_update_entity(hass, ZONE_1_ID)
        await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "one"


async def test_supported_features(hass):
    """Test supported features property."""
    await _setup_ws66i(hass, MockWs66i())

    state = hass.states.get(ZONE_1_ID)
    assert (
        SUPPORT_VOLUME_MUTE
        | SUPPORT_VOLUME_SET
        | SUPPORT_VOLUME_STEP
        | SUPPORT_TURN_ON
        | SUPPORT_TURN_OFF
        | SUPPORT_SELECT_SOURCE
        == state.attributes["supported_features"]
    )


async def test_source_list(hass):
    """Test source list property."""
    await _setup_ws66i(hass, MockWs66i())

    state = hass.states.get(ZONE_1_ID)
    # Note, the list is sorted!
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["one", "three"]


async def test_source_list_with_options(hass):
    """Test source list property."""
    await _setup_ws66i_with_options(hass, MockWs66i())

    state = hass.states.get(ZONE_1_ID)
    # Note, the list is sorted!
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["two", "four"]


async def test_select_source(hass):
    """Test source selection methods."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    await _call_media_player_service(
        hass,
        SERVICE_SELECT_SOURCE,
        {"entity_id": ZONE_1_ID, ATTR_INPUT_SOURCE: "three"},
    )
    assert ws66i.zones[11].source == 3

    # Trying to set unknown source
    await _call_media_player_service(
        hass,
        SERVICE_SELECT_SOURCE,
        {"entity_id": ZONE_1_ID, ATTR_INPUT_SOURCE: "no name"},
    )
    assert ws66i.zones[11].source == 3


async def test_unknown_source(hass):
    """Test behavior when device has unknown source."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    ws66i.set_source(11, 5)

    await async_update_entity(hass, ZONE_1_ID)
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes.get(ATTR_INPUT_SOURCE) is None


async def test_turn_on_off(hass):
    """Test turning on the zone."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    await _call_media_player_service(hass, SERVICE_TURN_OFF, {"entity_id": ZONE_1_ID})
    assert not ws66i.zones[11].power

    await _call_media_player_service(hass, SERVICE_TURN_ON, {"entity_id": ZONE_1_ID})
    assert ws66i.zones[11].power


async def test_mute_volume(hass):
    """Test mute functionality."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.5}
    )
    await _call_media_player_service(
        hass, SERVICE_VOLUME_MUTE, {"entity_id": ZONE_1_ID, "is_volume_muted": False}
    )
    assert not ws66i.zones[11].mute

    await _call_media_player_service(
        hass, SERVICE_VOLUME_MUTE, {"entity_id": ZONE_1_ID, "is_volume_muted": True}
    )
    assert ws66i.zones[11].mute


async def test_volume_up_down(hass):
    """Test increasing volume by one."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    assert ws66i.zones[11].volume == 0

    await _call_media_player_service(
        hass, SERVICE_VOLUME_DOWN, {"entity_id": ZONE_1_ID}
    )
    # should not go below zero
    assert ws66i.zones[11].volume == 0

    await _call_media_player_service(hass, SERVICE_VOLUME_UP, {"entity_id": ZONE_1_ID})
    assert ws66i.zones[11].volume == 1

    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    assert ws66i.zones[11].volume == 38

    await _call_media_player_service(hass, SERVICE_VOLUME_UP, {"entity_id": ZONE_1_ID})
    # should not go above 38
    assert ws66i.zones[11].volume == 38

    await _call_media_player_service(
        hass, SERVICE_VOLUME_DOWN, {"entity_id": ZONE_1_ID}
    )
    assert ws66i.zones[11].volume == 37


async def test_first_run_with_available_zones(hass):
    """Test first run with all zones available."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    registry = er.async_get(hass)

    entry = registry.async_get(ZONE_7_ID)
    assert not entry.disabled


async def test_first_run_with_failing_zones(hass):
    """Test first run with failed zones."""
    ws66i = MockWs66i()

    with patch.object(MockWs66i, "zone_status", return_value=None):
        await _setup_ws66i(hass, ws66i)

    registry = er.async_get(hass)

    entry = registry.async_get(ZONE_1_ID)
    assert not entry.disabled

    entry = registry.async_get(ZONE_7_ID)
    assert entry.disabled
    assert entry.disabled_by == er.DISABLED_INTEGRATION


async def test_not_first_run_with_failing_zone(hass):
    """Test first run with failed zones."""
    ws66i = MockWs66i()

    with patch.object(MockWs66i, "zone_status", return_value=None):
        await _setup_ws66i_not_first_run(hass, ws66i)

    registry = er.async_get(hass)

    entry = registry.async_get(ZONE_1_ID)
    assert not entry.disabled

    entry = registry.async_get(ZONE_7_ID)
    assert not entry.disabled


async def test_not_first_run_cant_connect(hass):
    """Test first run can't connect."""
    ws66i = MockWs66i()

    with patch.object(MockWs66i, "open", side_effect=ConnectionError):
        await _setup_ws66i_not_first_run(hass, ws66i)


async def test_unload_config_entry(hass):
    """Test unloading config entry."""
    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: MockWs66i(),
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        await config_entry.async_unload(hass)
