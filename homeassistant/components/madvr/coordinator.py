"""Coordinator for handling data fetching and updates."""

import logging

from madvr.madvr import Madvr

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type MadVRConfigEntry = ConfigEntry[MadVRCoordinator]


class MadVRCoordinator(DataUpdateCoordinator[dict]):
    """My custom coordinator for push-based API."""

    config_entry: MadVRConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MadVRConfigEntry,
        client: Madvr,
        name: str,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Madvr Coordinator",
        )
        self.entry_id = config_entry.entry_id
        self.client = client
        self.name = name
        self.client.set_update_callback(self.handle_push_data)
        _LOGGER.debug("MadVRCoordinator initialized")

    async def _async_update_data(self):
        """No-op method for initial setup."""
        return

    def handle_push_data(self, data: dict):
        """Handle new data pushed from the API."""
        _LOGGER.debug("Received push data: %s", data)
        self.async_set_updated_data(data)

    async def handle_coordinator_load(self):
        """Handle operations on integration load."""
        _LOGGER.debug("Using loop: %s", self.client.loop)
        # tell the library to start background tasks
        await self.client.async_add_tasks()
        _LOGGER.debug("Added %s tasks to client", len(self.client.tasks))

    async def async_handle_unload(self):
        """Handle unload."""
        _LOGGER.debug("Coordinator unloading")
        await self.client.async_cancel_tasks()
        self.client.stop()
        _LOGGER.debug("Coordinator closing connection")
        await self.client.close_connection()
        _LOGGER.debug("Unloaded")
