"""The Weheat integration."""

from __future__ import annotations

from weheat.abstractions.discovery import HeatPumpDiscovery

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .const import API_URL, LOGGER
from .coordinator import WeheatDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


type WeheatConfigEntry = ConfigEntry[list[WeheatDataUpdateCoordinator]]


async def async_setup_entry(hass: HomeAssistant, entry: WeheatConfigEntry) -> bool:
    """Set up Weheat from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    session = OAuth2Session(hass, entry, implementation)

    token = session.token["access_token"]
    entry.runtime_data = []

    # fetch a list of the heat pumps the entry can access
    for pump_info in await HeatPumpDiscovery.discover_active(API_URL, token):
        LOGGER.debug("Adding %s", pump_info)
        # for each pump, add a coordinator
        new_coordinator = WeheatDataUpdateCoordinator(
            hass=hass, session=session, heat_pump=pump_info
        )

        await new_coordinator.async_config_entry_first_refresh()

        entry.runtime_data.append(new_coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WeheatConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
