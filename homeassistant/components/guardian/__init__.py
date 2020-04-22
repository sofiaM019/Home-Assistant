"""The Elexa Guardian integration."""
import asyncio
from datetime import timedelta

from aioguardian import Client
from aioguardian.errors import GuardianError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DATA_CLIENT,
    DATA_DIAGNOSTICS,
    DATA_PAIR_DUMP,
    DATA_PING,
    DATA_SENSOR_STATUS,
    DATA_VALVE_STATUS,
    DATA_WIFI_STATUS,
    DOMAIN,
    LOGGER,
    TOPIC_UPDATE,
)

DATA_LISTENER = "listener"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

PLATFORMS = ["switch"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Elexa Guardian component."""
    hass.data[DOMAIN] = {DATA_CLIENT: {}, DATA_LISTENER: {}}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Elexa Guardian from a config entry."""
    hass.data[DOMAIN][DATA_CLIENT][entry.entry_id] = Guardian(hass, entry)
    await hass.data[DOMAIN][DATA_CLIENT][entry.entry_id].async_update()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    async def refresh(event_time):
        """Refresh data from the device."""
        await hass.data[DOMAIN][DATA_CLIENT][entry.entry_id].async_update()

    hass.data[DOMAIN][DATA_LISTENER][entry.entry_id] = async_track_time_interval(
        hass, refresh, DEFAULT_SCAN_INTERVAL
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
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
        remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(entry.entry_id)
        remove_listener()

    return unload_ok


class Guardian:
    """Define a class to communicate with the Guardian device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize."""
        self._hass = hass
        self.client = Client(entry.data[CONF_IP_ADDRESS])
        self.data = {}
        self.uid = entry.data["uid"]

    async def async_update(self):
        """Get updated data from the device."""
        async with self.client:
            tasks = {
                DATA_DIAGNOSTICS: self.client.device.diagnostics(),
                DATA_PAIR_DUMP: self.client.sensor.pair_dump(),
                DATA_PING: self.client.device.ping(),
                DATA_SENSOR_STATUS: self.client.sensor.sensor_status(),
                DATA_VALVE_STATUS: self.client.valve.valve_status(),
                DATA_WIFI_STATUS: self.client.device.wifi_status(),
            }

            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for data_category, result in zip(tasks, results):
            if isinstance(result, GuardianError):
                LOGGER.error("Error while fetching %s data: %s", data_category, result)
                self.data[data_category] = {}
                continue
            self.data[data_category] = result["data"]

        LOGGER.debug("Received new data: %s", self.data)
        async_dispatcher_send(self._hass, TOPIC_UPDATE.format(self.uid))


class GuardianEntity(Entity):
    """Define a base Guardian entity."""

    def __init__(self, guardian: Guardian):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: "Data provided by Elexa"}
        self._guardian = guardian
        self._name = guardian.data[DATA_DIAGNOSTICS]["codename"]

    @property
    def available(self):
        """Return whether the entity is available."""
        return bool(self._guardian.data[DATA_PING])

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._guardian.uid)},
            "manufacturer": "Elexa",
            "model": self._guardian.data[DATA_DIAGNOSTICS]["firmware"],
            "name": self._name,
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:water"

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._guardian.uid

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, TOPIC_UPDATE.format(self._guardian.uid), update
            )
        )

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self):
        """Update the entity."""
        raise NotImplementedError
