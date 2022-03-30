"""The tests for the utility_meter component."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.select.const import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.utility_meter.const import (
    DOMAIN,
    SERVICE_RESET,
    SERVICE_SELECT_NEXT_TARIFF,
    SERVICE_SELECT_TARIFF,
    SIGNAL_RESET_METER,
)
import homeassistant.components.utility_meter.sensor as um_sensor
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_PLATFORM,
    ENERGY_KILO_WATT_HOUR,
    EVENT_HOMEASSISTANT_START,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, mock_restore_cache


async def test_restore_state(hass):
    """Test utility sensor restore state."""
    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "tariffs": ["onpeak", "midpeak", "offpeak"],
            }
        }
    }
    mock_restore_cache(
        hass,
        [
            State(
                "select.energy_bill",
                "midpeak",
            ),
        ],
    )

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, Platform.SENSOR, config)
    await hass.async_block_till_done()

    # restore from cache
    state = hass.states.get("select.energy_bill")
    assert state.state == "midpeak"


async def test_services(hass):
    """Test energy sensor reset service."""
    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "cycle": "hourly",
                "tariffs": ["peak", "offpeak"],
            },
            "energy_bill2": {
                "source": "sensor.energy",
                "cycle": "hourly",
                "tariffs": ["peak", "offpeak"],
            },
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, Platform.SENSOR, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    entity_id = config[DOMAIN]["energy_bill"]["source"]
    hass.states.async_set(
        entity_id, 1, {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            3,
            {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "2"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "0"

    # Next tariff - only supported on legacy entity
    data = {ATTR_ENTITY_ID: "utility_meter.energy_bill"}
    await hass.services.async_call(DOMAIN, SERVICE_SELECT_NEXT_TARIFF, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            4,
            {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "2"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "1"

    # Change tariff
    data = {ATTR_ENTITY_ID: "select.energy_bill", "option": "wrong_tariff"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    # Inexisting tariff, ignoring
    assert hass.states.get("select.energy_bill").state != "wrong_tariff"

    data = {ATTR_ENTITY_ID: "select.energy_bill", "option": "peak"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            5,
            {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "3"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "1"

    # Reset meters
    data = {ATTR_ENTITY_ID: "select.energy_bill"}
    await hass.services.async_call(DOMAIN, SERVICE_RESET, data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "0"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "0"

    # meanwhile energy_bill2_peak accumulated all kWh
    state = hass.states.get("sensor.energy_bill2_peak")
    assert state.state == "4"


async def test_services_config_entry(hass):
    """Test energy sensor reset service."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Energy bill",
            "net_consumption": False,
            "offset": 0,
            "source": "sensor.energy",
            "tariffs": "peak,offpeak",
        },
        title="Energy bill",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Energy bill2",
            "net_consumption": False,
            "offset": 0,
            "source": "sensor.energy",
            "tariffs": "peak,offpeak",
        },
        title="Energy bill2",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    entity_id = "sensor.energy"
    hass.states.async_set(
        entity_id, 1, {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            3,
            {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "2"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "0"

    # Next tariff - only supported on legacy entity
    with pytest.raises(ServiceNotFound):
        data = {ATTR_ENTITY_ID: "utility_meter.energy_bill"}
        await hass.services.async_call(DOMAIN, SERVICE_SELECT_NEXT_TARIFF, data)
        await hass.async_block_till_done()

    # Change tariff
    data = {ATTR_ENTITY_ID: "select.energy_bill", "option": "offpeak"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            4,
            {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "2"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "1"

    # Change tariff
    data = {ATTR_ENTITY_ID: "select.energy_bill", "option": "wrong_tariff"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    # Inexisting tariff, ignoring
    assert hass.states.get("select.energy_bill").state != "wrong_tariff"

    data = {ATTR_ENTITY_ID: "select.energy_bill", "option": "peak"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            5,
            {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "3"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "1"

    # Reset meters
    data = {ATTR_ENTITY_ID: "select.energy_bill"}
    await hass.services.async_call(DOMAIN, SERVICE_RESET, data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "0"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "0"

    # meanwhile energy_bill2_peak accumulated all kWh
    state = hass.states.get("sensor.energy_bill2_peak")
    assert state.state == "4"


async def test_cron(hass, legacy_patchable_time):
    """Test cron pattern."""

    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "cron": "*/5 * * * *",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)


async def test_cron_and_meter(hass, legacy_patchable_time):
    """Test cron pattern and meter type fails."""
    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "cycle": "hourly",
                "cron": "0 0 1 * *",
            }
        }
    }

    assert not await async_setup_component(hass, DOMAIN, config)


async def test_both_cron_and_meter(hass, legacy_patchable_time):
    """Test cron pattern and meter type passes in different meter."""
    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "cron": "0 0 1 * *",
            },
            "water_bill": {
                "source": "sensor.water",
                "cycle": "hourly",
            },
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)


async def test_cron_and_offset(hass, legacy_patchable_time):
    """Test cron pattern and offset fails."""

    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "offset": {"days": 1},
                "cron": "0 0 1 * *",
            }
        }
    }

    assert not await async_setup_component(hass, DOMAIN, config)


async def test_bad_cron(hass, legacy_patchable_time):
    """Test bad cron pattern."""

    config = {
        "utility_meter": {"energy_bill": {"source": "sensor.energy", "cron": "*"}}
    }

    assert not await async_setup_component(hass, DOMAIN, config)


async def test_setup_missing_discovery(hass):
    """Test setup with configuration missing discovery_info."""
    assert not await um_sensor.async_setup_platform(hass, {CONF_PLATFORM: DOMAIN}, None)


async def test_legacy_support(hass):
    """Test legacy entity support."""
    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "cycle": "hourly",
                "tariffs": ["peak", "offpeak"],
            },
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, Platform.SENSOR, config)
    await hass.async_block_till_done()

    select_state = hass.states.get("select.energy_bill")
    legacy_state = hass.states.get("utility_meter.energy_bill")

    assert select_state.state == legacy_state.state == "peak"
    select_attributes = select_state.attributes
    legacy_attributes = legacy_state.attributes
    assert select_attributes.keys() == {
        "friendly_name",
        "icon",
        "options",
    }
    assert legacy_attributes.keys() == {"friendly_name", "icon", "tariffs"}
    assert select_attributes["friendly_name"] == legacy_attributes["friendly_name"]
    assert select_attributes["icon"] == legacy_attributes["icon"]
    assert select_attributes["options"] == legacy_attributes["tariffs"]

    # Change tariff on the select
    data = {ATTR_ENTITY_ID: "select.energy_bill", "option": "offpeak"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    select_state = hass.states.get("select.energy_bill")
    legacy_state = hass.states.get("utility_meter.energy_bill")
    assert select_state.state == legacy_state.state == "offpeak"

    # Change tariff on the legacy entity
    data = {ATTR_ENTITY_ID: "utility_meter.energy_bill", "tariff": "offpeak"}
    await hass.services.async_call(DOMAIN, SERVICE_SELECT_TARIFF, data)
    await hass.async_block_till_done()

    select_state = hass.states.get("select.energy_bill")
    legacy_state = hass.states.get("utility_meter.energy_bill")
    assert select_state.state == legacy_state.state == "offpeak"

    # Cycle tariffs on the select - not supported
    data = {ATTR_ENTITY_ID: "select.energy_bill"}
    await hass.services.async_call(DOMAIN, SERVICE_SELECT_NEXT_TARIFF, data)
    await hass.async_block_till_done()

    select_state = hass.states.get("select.energy_bill")
    legacy_state = hass.states.get("utility_meter.energy_bill")
    assert select_state.state == legacy_state.state == "offpeak"

    # Cycle tariffs on the legacy entity
    data = {ATTR_ENTITY_ID: "utility_meter.energy_bill"}
    await hass.services.async_call(DOMAIN, SERVICE_SELECT_NEXT_TARIFF, data)
    await hass.async_block_till_done()

    select_state = hass.states.get("select.energy_bill")
    legacy_state = hass.states.get("utility_meter.energy_bill")
    assert select_state.state == legacy_state.state == "peak"

    # Reset the legacy entity
    reset_calls = []

    def async_reset_meter(entity_id):
        reset_calls.append(entity_id)

    async_dispatcher_connect(hass, SIGNAL_RESET_METER, async_reset_meter)

    data = {ATTR_ENTITY_ID: "utility_meter.energy_bill"}
    await hass.services.async_call(DOMAIN, SERVICE_RESET, data)
    await hass.async_block_till_done()
    assert reset_calls == ["select.energy_bill"]


@pytest.mark.parametrize(
    "tariffs,expected_entities",
    (
        (
            "",
            ["sensor.electricity_meter"],
        ),
        (
            "high,low",
            [
                "sensor.electricity_meter_low",
                "sensor.electricity_meter_high",
                "select.electricity_meter",
            ],
        ),
    ),
)
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant, tariffs: str, expected_entities: list[str]
) -> None:
    """Test setting up and removing a config entry."""
    input_sensor_entity_id = "sensor.input"
    registry = er.async_get(hass)

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Electricity meter",
            "net_consumption": False,
            "offset": 0,
            "source": input_sensor_entity_id,
            "tariffs": tariffs,
        },
        title="Electricity meter",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == len(expected_entities)
    assert len(registry.entities) == len(expected_entities)
    for entity in expected_entities:
        assert hass.states.get(entity)
        assert entity in registry.entities

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert len(hass.states.async_all()) == 0
    assert len(registry.entities) == 0
