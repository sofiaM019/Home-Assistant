"""DataUpdateCoordinator for the Hydrawise integration."""

from __future__ import annotations

from datetime import timedelta

from hydrawiser.core import Hydrawiser

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class HydrawiseDataUpdateCoordinator(DataUpdateCoordinator):
    """The Hydrawise Data Update Coordinator."""

    def __init__(
        self, hass: HomeAssistant, api: Hydrawiser, scan_interval: timedelta
    ) -> None:
        """Initialize HydrawiseDataUpdateCoordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=scan_interval)
        self.api = api

    async def _async_update_data(self):
        """Fetch the latest data from Hydrawise."""
        result = await self.hass.async_add_executor_job(self.api.update_controller_info)
        if not result:
            raise UpdateFailed("Failed to refresh Hydrawise data")
