"""Tests for the Freedompro integration."""
from unittest.mock import patch

from homeassistant.components.freedompro.const import DOMAIN

from tests.common import MockConfigEntry
from tests.components.freedompro.const import DEVICES, DEVICES_STATE


async def init_integration(hass) -> MockConfigEntry:
    """Set up the Freedompro integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Feedompro",
        unique_id="0123456",
        data={
            "api_key": "gdhsksjdhcncjdkdjndjdkdmndjdjdkd",
        },
    )

    with patch(
        "homeassistant.components.freedompro.list",
        return_value={
            "state": True,
            "devices": DEVICES,
        },
    ), patch(
        "homeassistant.components.freedompro.getStates",
        return_value=DEVICES_STATE,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
