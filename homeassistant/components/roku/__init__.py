"""Support for Roku."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

from rokuecp import Roku, RokuError
from rokuecp.models import Device
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_NAME, CONF_HOST
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    DOMAIN,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list, [vol.Schema({vol.Required(CONF_HOST): cv.string})]
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [MEDIA_PLAYER_DOMAIN, REMOTE_DOMAIN]
SCAN_INTERVAL = timedelta(seconds=20)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: Dict) -> bool:
    """Set up the Roku integration."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN in config:
        for entry_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config,
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up Roku from a config entry."""
    coordinator = RokuDataUpdateCoordinator(hass, host=entry.data[CONF_HOST])
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class RokuDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Roku data."""

    def __init__(
        self, hass: HomeAssistantType, *, host: str,
    ):
        """Initialize global Roku data updater."""
        self.roku = Roku(host=host, session=async_get_clientsession(hass))

        self.full_update_interval = timedelta(minutes=15)
        self.full_update_required = True
        self._unsub_full_update: Optional[CALLBACK_TYPE] = None

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> Device:
        """Fetch data from Roku."""
        full_update = self.full_update_required

        try:
            data = await self.roku.update(full_update=full_update)

            if full_update:
                self.full_update_required = False
                self._schedule_full_update()

            return data
        except RokuError as error:
            raise UpdateFailed(f"Invalid response from API: {error}")

    @callback
    def _schedule_full_update(self) -> None:
        """Schedule a full update."""
        if self._unsub_full_update:
            self._unsub_full_update()
            self._unsub_full_update = None

        # We _floor_ utcnow to create a schedule on a rounded second,
        # minimizing the time between the point and the real activation.
        # That way we obtain a constant update frequency,
        # as long as the update process takes less than a second
        self._unsub_full_update = async_track_point_in_utc_time(
            self.hass,
            self._handle_full_update_interval,
            utcnow().replace(microsecond=0) + self.full_update_interval,
        )

    async def _handle_full_update_interval(self, _now: datetime) -> None:
        """Handle a full update interval occurrence."""
        self._unsub_full_update = None
        self.full_update_required = True
        await self.async_request_refresh()


class RokuEntity(Entity):
    """Defines a base Roku entity."""

    def __init__(
        self, *, device_id: str, name: str, coordinator: RokuDataUpdateCoordinator
    ) -> None:
        """Initialize the Roku entity."""
        self._device_id = device_id
        self._name = name
        self.coordinator = coordinator

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Update an Roku entity."""
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this Roku device."""
        if self._device_id is None:
            return None

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._device_id)},
            ATTR_NAME: self.name,
            ATTR_MANUFACTURER: self.coordinator.data.info.brand,
            ATTR_MODEL: self.coordinator.data.info.model_name,
            ATTR_SOFTWARE_VERSION: self.coordinator.data.info.version,
        }
