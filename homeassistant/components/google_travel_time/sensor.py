"""Support for Google travel time sensors."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Callable

import googlemaps
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    TIME_MINUTES,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import location
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

from .const import (
    ALL_LANGUAGES,
    ATTRIBUTION,
    AVOID,
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_LANGUAGE,
    CONF_OPTIONS,
    CONF_ORIGIN,
    CONF_TRAFFIC_MODEL,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_TRAVEL_MODE,
    CONF_UNITS,
    DEFAULT_NAME,
    DOMAIN,
    TRANSIT_PREFS,
    TRANSPORT_TYPE,
    TRAVEL_MODE,
    TRAVEL_MODEL,
    UNITS,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_DESTINATION): cv.string,
        vol.Required(CONF_ORIGIN): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_TRAVEL_MODE): vol.In(TRAVEL_MODE),
        vol.Optional(CONF_OPTIONS, default={CONF_MODE: "driving"}): vol.All(
            dict,
            vol.Schema(
                {
                    vol.Optional(CONF_MODE, default="driving"): vol.In(TRAVEL_MODE),
                    vol.Optional(CONF_LANGUAGE): vol.In(ALL_LANGUAGES),
                    vol.Optional(CONF_AVOID): vol.In(AVOID),
                    vol.Optional(CONF_UNITS): vol.In(UNITS),
                    vol.Exclusive(CONF_ARRIVAL_TIME, "time"): cv.string,
                    vol.Exclusive(CONF_DEPARTURE_TIME, "time"): cv.string,
                    vol.Optional(CONF_TRAFFIC_MODEL): vol.In(TRAVEL_MODEL),
                    vol.Optional(CONF_TRANSIT_MODE): vol.In(TRANSPORT_TYPE),
                    vol.Optional(CONF_TRANSIT_ROUTING_PREFERENCE): vol.In(
                        TRANSIT_PREFS
                    ),
                }
            ),
        ),
    }
)

TRACKABLE_DOMAINS = ["device_tracker", "sensor", "zone", "person"]
DATA_KEY = "google_travel_time"


def convert_time_to_utc(timestr):
    """Take a string like 08:00:00 and convert it to a unix timestamp."""
    combined = datetime.combine(
        dt_util.start_of_local_day(), dt_util.parse_time(timestr)
    )
    if combined < datetime.now():
        combined = combined + timedelta(days=1)
    return dt_util.as_timestamp(combined)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[SensorEntity], bool], None],
) -> None:
    """Set up a Google travel time sensor entry."""
    name = None
    if not config_entry.options:
        new_data = config_entry.data.copy()
        options = new_data.pop(CONF_OPTIONS, {})
        name = new_data.pop(CONF_NAME, None)

        if CONF_UNITS not in options:
            options[CONF_UNITS] = hass.config.units.name

        if CONF_TRAVEL_MODE in new_data:
            wstr = (
                "Google Travel Time: travel_mode is deprecated, please "
                "add mode to the options dictionary instead!"
            )
            _LOGGER.warning(wstr)
            travel_mode = new_data.pop(CONF_TRAVEL_MODE)
            if CONF_MODE not in options:
                options[CONF_MODE] = travel_mode

        if CONF_MODE not in options:
            options[CONF_MODE] = "driving"

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=options
        )

    hass.data.setdefault(DATA_KEY, [])

    api_key = config_entry.data[CONF_API_KEY]
    origin = config_entry.data[CONF_ORIGIN]
    destination = config_entry.data[CONF_DESTINATION]
    name = name or f"{DEFAULT_NAME}: {origin} -> {destination}"

    client = googlemaps.Client(api_key, timeout=10)

    sensor = GoogleTravelTimeSensor(
        hass, config_entry, name, api_key, origin, destination, client
    )
    hass.data[DATA_KEY].append(sensor)

    async_add_entities([sensor], False)


async def async_setup_platform(
    hass: HomeAssistant, config, add_entities_callback, discovery_info=None
):
    """Set up the Google travel time platform."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )

    _LOGGER.warning(
        "Your Google travel time configuration has been imported into the UI; "
        "please remove it from configuration.yaml as support for it will be "
        "removed in a future release"
    )


class GoogleTravelTimeSensor(SensorEntity):
    """Representation of a Google travel time sensor."""

    def __init__(self, hass, config_entry, name, api_key, origin, destination, client):
        """Initialize the sensor."""
        self._hass = hass
        self._name = name
        self._config_entry = config_entry
        self._unit_of_measurement = TIME_MINUTES
        self._matrix = None
        self._api_key = api_key
        self._unique_id = config_entry.unique_id
        self.valid_api_connection = True

        # Check if location is a trackable entity
        if origin.split(".", 1)[0] in TRACKABLE_DOMAINS:
            self._origin_entity_id = origin
        else:
            self._origin = origin

        if destination.split(".", 1)[0] in TRACKABLE_DOMAINS:
            self._destination_entity_id = destination
        else:
            self._destination = destination

        self._client = client

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added."""
        if self.hass.state != CoreState.running:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, lambda _: self.first_update()
            )
        else:
            self.hass.async_add_executor_job(self.first_update)

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._matrix is None:
            return None

        _data = self._matrix["rows"][0]["elements"][0]
        if "duration_in_traffic" in _data:
            return round(_data["duration_in_traffic"]["value"] / 60)
        if "duration" in _data:
            return round(_data["duration"]["value"] / 60)
        return None

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": DOMAIN,
            "identifiers": {(DOMAIN, self._api_key)},
            "entry_type": "service",
        }

    @property
    def unique_id(self) -> str:
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._matrix is None:
            return None

        res = self._matrix.copy()
        options = self._config_entry.options.copy()
        res.update(options)
        del res["rows"]
        _data = self._matrix["rows"][0]["elements"][0]
        if "duration_in_traffic" in _data:
            res["duration_in_traffic"] = _data["duration_in_traffic"]["text"]
        if "duration" in _data:
            res["duration"] = _data["duration"]["text"]
        if "distance" in _data:
            res["distance"] = _data["distance"]["text"]
        res["origin"] = self._origin
        res["destination"] = self._destination
        res[ATTR_ATTRIBUTION] = ATTRIBUTION
        return res

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    def first_update(self):
        """Validate the connection on first update."""
        try:
            self.update()
        except googlemaps.exceptions.ApiError as exp:
            _LOGGER.error(exp)
            self.valid_api_connection = False
            return

    def update(self):
        """Get the latest data from Google."""
        options_copy = self._config_entry.options.copy()
        dtime = options_copy.get(CONF_DEPARTURE_TIME)
        atime = options_copy.get(CONF_ARRIVAL_TIME)
        if dtime is not None and ":" in dtime:
            options_copy[CONF_DEPARTURE_TIME] = convert_time_to_utc(dtime)
        elif dtime is not None:
            options_copy[CONF_DEPARTURE_TIME] = dtime
        elif atime is None:
            options_copy[CONF_DEPARTURE_TIME] = "now"

        if atime is not None and ":" in atime:
            options_copy[CONF_ARRIVAL_TIME] = convert_time_to_utc(atime)
        elif atime is not None:
            options_copy[CONF_ARRIVAL_TIME] = atime

        # Convert device_trackers to google friendly location
        if hasattr(self, "_origin_entity_id"):
            self._origin = self._get_location_from_entity(self._origin_entity_id)

        if hasattr(self, "_destination_entity_id"):
            self._destination = self._get_location_from_entity(
                self._destination_entity_id
            )

        self._destination = self._resolve_zone(self._destination)
        self._origin = self._resolve_zone(self._origin)

        if self._destination is not None and self._origin is not None:
            self._matrix = self._client.distance_matrix(
                self._origin, self._destination, **options_copy
            )

    def _get_location_from_entity(self, entity_id):
        """Get the location from the entity state or attributes."""
        entity = self._hass.states.get(entity_id)

        if entity is None:
            _LOGGER.error("Unable to find entity %s", entity_id)
            self.valid_api_connection = False
            return None

        # Check if the entity has location attributes
        if location.has_location(entity):
            return self._get_location_from_attributes(entity)

        # Check if device is in a zone
        zone_entity = self._hass.states.get("zone.%s" % entity.state)
        if location.has_location(zone_entity):
            _LOGGER.debug(
                "%s is in %s, getting zone location", entity_id, zone_entity.entity_id
            )
            return self._get_location_from_attributes(zone_entity)

        # If zone was not found in state then use the state as the location
        if entity_id.startswith("sensor."):
            return entity.state

        # When everything fails just return nothing
        return None

    @staticmethod
    def _get_location_from_attributes(entity):
        """Get the lat/long string from an entities attributes."""
        attr = entity.attributes
        return f"{attr.get(ATTR_LATITUDE)},{attr.get(ATTR_LONGITUDE)}"

    def _resolve_zone(self, friendly_name):
        entities = self._hass.states.all()
        for entity in entities:
            if entity.domain == "zone" and entity.name == friendly_name:
                return self._get_location_from_attributes(entity)

        return friendly_name
