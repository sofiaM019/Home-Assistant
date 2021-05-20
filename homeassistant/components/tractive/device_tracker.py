"""Support for Tractive device trackers."""

import asyncio
import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN,
    SERVER_UNAVAILABLE,
    TRACKER_HARDWARE_STATUS_UPDATED,
    TRACKER_POSITION_UPDATED,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Tractive device trackers."""
    client = hass.data[DOMAIN][entry.entry_id]

    trackables = await client.trackable_objects()

    entities = await asyncio.gather(
        *[create_trackable_entity(client, trackable) for trackable in trackables]
    )

    async_add_entities(entities)


async def create_trackable_entity(client, trackable):
    """Create an entity instance."""
    trackable = await trackable.details()
    tracker = client.tracker(trackable["device_id"])

    tracker_details, hw_info, pos_report = await asyncio.gather(
        tracker.details(), tracker.hw_info(), tracker.pos_report()
    )

    return TractiveDeviceTracker(
        client, trackable, tracker_details, hw_info, pos_report
    )


class TractiveDeviceTracker(TrackerEntity):
    """Tractive device tracker."""

    def __init__(self, client, trackable, tracker_details, hw_info, pos_report):
        """Initialize tracker entity."""
        self._client = client
        self._trackable = trackable
        self._tracker_details = tracker_details
        self._hw_info = hw_info

        self._battery_level = hw_info["battery_level"]
        self._latitude = pos_report["latlong"][0]
        self._longitude = pos_report["latlong"][1]
        self._accuracy = pos_report["pos_uncertainty"]
        self._tracker_id = self._tracker_details["_id"]

    @property
    def name(self):
        """Return the name of the sensor."""
        pet_name = self._trackable["details"]["name"]
        return f"{self._tracker_id} {pet_name}"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return self._trackable["_id"]

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:paw"

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._tracker_id)},
            "name": f"Tractive ({self._tracker_id})",
            "manufacturer": "Tractive GmbH",
            "sw_version": self._tracker_details["fw_version"],
            "entry_type": None,
            "model": self._tracker_details["model_number"],
        }

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._longitude

    @property
    def location_accuracy(self):
        """Return the gps accuracy of the device."""
        return self._accuracy

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self._battery_level

    async def async_added_to_hass(self):
        """Handle entity which will be added."""

        @callback
        def handle_hardware_status_update(event):
            self._battery_level = event["battery_level"]
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TRACKER_HARDWARE_STATUS_UPDATED}-{self._tracker_id}",
                handle_hardware_status_update,
            )
        )

        @callback
        def handle_position_update(event):
            self._latitude = event["latitude"]
            self._longitude = event["longitude"]
            self._accuracy = event["accuracy"]
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TRACKER_POSITION_UPDATED}-{self._tracker_id}",
                handle_position_update,
            )
        )

        @callback
        def handle_server_unavailable():
            self._latitude = None
            self._longitude = None
            self._accuracy = None
            self._battery_level = None
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_UNAVAILABLE}-{self._client.user_id}",
                handle_server_unavailable,
            )
        )
