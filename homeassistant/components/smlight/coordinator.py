"""DataUpdateCoordinator for Smlight."""

from dataclasses import dataclass
import socket

from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError
from pysmlight.web import Api2, Info, Sensors

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.network import is_ip_address

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


@dataclass
class SmData:
    """SMLIGHT data stored in the DataUpdateCoordinator."""

    sensors: Sensors
    info: Info


class SmDataUpdateCoordinator(DataUpdateCoordinator[SmData]):
    """Class to manage fetching SMLIGHT data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=SCAN_INTERVAL,
        )

        self.hostname = self.get_hostname(host)
        self.unique_id: str | None = None

        self.client = Api2(host=host, session=async_get_clientsession(hass))

    def get_hostname(self, host: str) -> str:
        """Get hostname. Fallback to IP if not available."""
        if is_ip_address(host):
            try:
                host = socket.gethostbyaddr(host)[0]
            except socket.herror:
                return host
        return host.split(".", maxsplit=1)[0]

    async def _async_setup(self) -> None:
        """Authenticate if needed during initial setup."""
        if await self.client.check_auth_needed():
            if (
                CONF_USERNAME in self.config_entry.data
                and CONF_PASSWORD in self.config_entry.data
            ):
                try:
                    await self.client.authenticate(
                        self.config_entry.data[CONF_USERNAME],
                        self.config_entry.data[CONF_PASSWORD],
                    )
                except SmlightAuthError as err:
                    LOGGER.error("Failed to authenticate: %s", err)
                    raise ConfigEntryError from err

        info = await self.client.get_info()
        self.unique_id = format_mac(info.MAC)

    async def _async_update_data(self) -> SmData:
        """Fetch data from the SMLIGHT device."""
        try:
            return SmData(
                sensors=await self.client.get_sensors(),
                info=await self.client.get_info(),
            )
        except SmlightConnectionError as err:
            raise UpdateFailed(err) from err
