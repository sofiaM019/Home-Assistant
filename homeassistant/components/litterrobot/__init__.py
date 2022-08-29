"""The Litter-Robot integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, SupportedModels
from .hub import LitterRobotHub

PLATFORMS = [
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]

PLATFORMS_BY_TYPE = {
    SupportedModels.LITTER_ROBOT: [
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
        Platform.VACUUM,
    ],
    SupportedModels.LITTER_ROBOT_3: [
        Platform.BUTTON,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
        Platform.VACUUM,
    ],
    SupportedModels.LITTER_ROBOT_4: [
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
        Platform.VACUUM,
    ],
    SupportedModels.FEEDER_ROBOT: [
        Platform.BUTTON,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Litter-Robot from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hub = hass.data[DOMAIN][entry.entry_id] = LitterRobotHub(hass, entry.data)
    await hub.login(load_robots=True)

    platforms = set()
    for robot in hub.account.robots:
        platforms.update(PLATFORMS_BY_TYPE[type(robot)])
    if platforms:
        await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    await hub.account.disconnect()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
