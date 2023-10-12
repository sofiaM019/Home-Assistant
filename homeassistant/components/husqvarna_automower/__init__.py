"""The Husqvarna Automower integration."""

import contextlib
import logging

from aioautomower.session import AutomowerSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import api
from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [
    Platform.LAWN_MOWER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    automower_api = AutomowerSession(
        api.AsyncConfigEntryAuth(
            aiohttp_client.async_get_clientsession(hass),
            session,
        )
    )

    coordinator = AutomowerDataUpdateCoordinator(hass, automower_api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unload of an entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    with contextlib.suppress(Exception):
        await coordinator.api.close()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
