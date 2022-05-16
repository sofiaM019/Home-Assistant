"""The StarLine component."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady

from .account import StarlineAccount
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_SET_SCAN_INTERVAL,
    SERVICE_UPDATE_STATE,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the StarLine device from a config entry."""
    account = StarlineAccount(hass, entry)
    await account.update()
    if not account.api.available:
        raise ConfigEntryNotReady

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = account

    device_registry = await hass.helpers.device_registry.async_get_registry()
    for device in account.api.devices.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **account.device_info(device)
        )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def async_set_scan_interval(call: ServiceCall) -> None:
        """Set scan interval."""
        options = dict(entry.options)
        options[CONF_SCAN_INTERVAL] = call.data[CONF_SCAN_INTERVAL]
        hass.config_entries.async_update_entry(entry=entry, options=options)

    async def async_update(call: ServiceCall | None = None) -> None:
        """Update all data."""
        await account.update()

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_STATE, async_update)
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCAN_INTERVAL,
        async_set_scan_interval,
        schema=vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=10)
                )
            }
        ),
    )

    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    await async_options_updated(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    account: StarlineAccount = hass.data[DOMAIN][config_entry.entry_id]
    account.unload()
    return unload_ok


async def async_options_updated(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Triggered by config entry options updates."""
    account: StarlineAccount = hass.data[DOMAIN][config_entry.entry_id]
    scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    account.set_update_interval(scan_interval)
