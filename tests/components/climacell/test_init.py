"""Tests for Climacell init."""
from datetime import timedelta
import logging

import pytest

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_DOMAIN
from homeassistant.components.climacell.config_flow import (
    _get_config_schema,
    _get_unique_id,
)
from homeassistant.components.climacell.const import DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.helpers.typing import HomeAssistantType

from .const import MIN_CONFIG

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_load_and_unload(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test loading and unloading entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_get_config_schema(hass)(MIN_CONFIG),
        unique_id=_get_unique_id(hass, _get_config_schema(hass)(MIN_CONFIG)),
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(AIR_QUALITY_DOMAIN)) == 0

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 0
    assert len(hass.states.async_entity_ids(AIR_QUALITY_DOMAIN)) == 0


async def test_update_interval(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test that update_interval changes based on number of entries."""
    config = _get_config_schema(hass)(MIN_CONFIG)
    for i in range(0, 2):
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=config, unique_id=_get_unique_id(hass, config) + str(i)
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.data[DOMAIN][config_entry.entry_id].update_interval == timedelta(
            minutes=(4 + (i * 3))
        )
