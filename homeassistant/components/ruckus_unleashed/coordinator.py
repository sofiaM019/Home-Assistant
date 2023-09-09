"""Ruckus Unleashed DataUpdateCoordinator."""
from datetime import timedelta
import logging

from aioruckus import AjaxSession
from aioruckus.exceptions import AuthenticationError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_CLIENT_MAC, DOMAIN, KEY_SYS_CLIENTS, SCAN_INTERVAL

_LOGGER = logging.getLogger(__package__)


class RuckusUnleashedDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data from Ruckus Unleashed client."""

    def __init__(self, hass: HomeAssistant, *, ruckus: AjaxSession) -> None:
        """Initialize global Ruckus Unleashed data updater."""
        self.ruckus = ruckus

        update_interval = timedelta(seconds=SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _fetch_clients(self) -> dict:
        """Fetch clients from the API and format them."""
        clients = await self.ruckus.api.get_active_clients()
        _LOGGER.debug("fetched %d active clients", len(clients))
        return {client[API_CLIENT_MAC]: client for client in clients}

    async def _async_update_data(self) -> dict:
        """Fetch Ruckus Unleashed data."""
        try:
            return {KEY_SYS_CLIENTS: await self._fetch_clients()}
        except AuthenticationError as autherror:
            raise UpdateFailed(autherror) from autherror
        except (ConnectionRefusedError, ConnectionError) as conerr:
            raise UpdateFailed(conerr) from conerr
