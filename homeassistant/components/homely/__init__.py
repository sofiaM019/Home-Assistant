"""The homely integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from requests import ConnectTimeout, HTTPError

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homelypy.devices import SingleLocation, WindowSensor
from homelypy.homely import ConnectionFailedException, Homely

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up homely from a config entry."""

    username = entry.data["username"]
    password = entry.data["password"]
    location_id = entry.data["location_id"]

    try:
        homely = Homely(username, password)
        await hass.async_add_executor_job(homely.get_location, location_id)
    except (ConnectionFailedException, ConnectTimeout, HTTPError) as ex:
        raise ConfigEntryNotReady(f"Unable to connect to Homely: {ex}") from ex

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = homely

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    # hass.async_create_task(
    #     discovery.async_load_platform(
    #         hass,
    #         Platform.NOTIFY,
    #         DOMAIN,
    #         {CONF_NAME: DOMAIN},
    #         hass.data[DATA_HASS_CONFIG],
    #     )
    # )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class PollingDataCoordinator(DataUpdateCoordinator):
    """Homely polling data coordinator."""

    def __init__(
        self, hass: HomeAssistant, homely: Homely, location: SingleLocation
    ) -> None:
        """Initialise homely connection."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Homely {location.name}",
            update_interval=timedelta(minutes=5),
        )
        self.homely = homely
        self.location = location
        self.added_sensors: set[str] = set()

    async def _async_update_data(self) -> None:
        self.location = await self.hass.async_add_executor_job(
            self.homely.get_location, self.location.location_id
        )


class WindowSensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Homely window sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(self, coordinator, device_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.device_id = device_id

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device: WindowSensor = next(
            filter(
                lambda device: (device.id == self.device_id),
                self.coordinator.location.devices,
            )
        )
        self._attr_is_on = device.alarm.alarm
        self.async_write_ha_state()
