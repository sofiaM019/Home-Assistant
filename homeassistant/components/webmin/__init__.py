"""The Webmin integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WebminUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Webmin from a config entry."""

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = WebminUpdateCoordinator(
        hass, entry
    )
    await hass.data[DOMAIN][entry.entry_id].async_config_entry_first_refresh()
    await hass.data[DOMAIN][entry.entry_id].async_setup()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
