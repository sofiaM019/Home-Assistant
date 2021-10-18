"""The Broadlink integration."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging

from homeassistant.const import CONF_TYPE

from .const import CONF_PRODUCT_ID, DOMAIN
from .device import BroadlinkDevice
from .heartbeat import BroadlinkHeartbeat

_LOGGER = logging.getLogger(__name__)


@dataclass
class BroadlinkData:
    """Class for sharing data within the Broadlink integration."""

    devices: dict = field(default_factory=dict)
    platforms: dict = field(default_factory=dict)
    heartbeat: BroadlinkHeartbeat | None = None


async def async_setup(hass, config):
    """Set up the Broadlink integration."""
    hass.data[DOMAIN] = BroadlinkData()
    return True


async def async_setup_entry(hass, entry):
    """Set up a Broadlink device from a config entry."""
    data = hass.data[DOMAIN]

    if data.heartbeat is None:
        data.heartbeat = BroadlinkHeartbeat(hass)
        hass.async_create_task(data.heartbeat.async_setup())

    device = BroadlinkDevice(hass, entry)
    return await device.async_setup()


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    data = hass.data[DOMAIN]

    device = data.devices.pop(entry.entry_id)
    result = await device.async_unload()

    if not data.devices:
        await data.heartbeat.async_unload()
        data.heartbeat = None

    return result


async def async_migrate_entry(hass, entry):
    """Migrate a config entry."""
    if entry.version == 1:
        new = {**entry.data}

        new[CONF_PRODUCT_ID] = new.pop(CONF_TYPE)

        entry.data = {**new}
        entry.version = 2

        _LOGGER.info("Migration to version %s successful", entry.version)

    return True
