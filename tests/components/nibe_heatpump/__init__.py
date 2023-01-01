"""Tests for the Nibe Heat Pump integration."""

from typing import Any

from homeassistant.components.nibe_heatpump import DOMAIN, Coordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def async_add_and_get_entry(
    hass: HomeAssistant, data: dict[str, Any]
) -> Coordinator:
    """Add entry and get the coordinator."""
    entry = MockConfigEntry(domain=DOMAIN, title="Dummy", data=data)

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    return hass.data[DOMAIN][entry.entry_id]
