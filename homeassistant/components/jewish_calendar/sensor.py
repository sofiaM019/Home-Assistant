"""Platform to retrieve Jewish calendar information for Home Assistant."""
from __future__ import annotations

from datetime import datetime
import logging

import hdate

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from . import DOMAIN
from .const import DATA_SENSORS, TIME_SENSORS

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Set up the Jewish calendar sensor platform."""
    if discovery_info is None:
        return

    sensors = [
        JewishCalendarSensor(hass.data[DOMAIN], description)
        for description in DATA_SENSORS
    ]
    sensors.extend(
        JewishCalendarTimeSensor(hass.data[DOMAIN], description)
        for description in TIME_SENSORS
    )

    async_add_entities(sensors)


class JewishCalendarSensor(SensorEntity):
    """Representation of an Jewish calendar sensor."""

    def __init__(self, data, description: SensorEntityDescription) -> None:
        """Initialize the Jewish calendar sensor."""
        self._description = description
        self._type = description.key
        self._attr_name = f"{data['name']} {self._description.name}"
        self._attr_unique_id = f"{data['prefix']}_{self._type}"
        self._location = data["location"]
        self._hebrew = data["language"] == "hebrew"
        self._candle_lighting_offset = data["candle_lighting_offset"]
        self._havdalah_offset = data["havdalah_offset"]
        self._diaspora = data["diaspora"]
        self._state = None
        self._holiday_attrs: dict[str, str] = {}

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if isinstance(self._state, datetime):
            return self._state.isoformat()
        return self._state

    async def async_update(self):
        """Update the state of the sensor."""
        now = dt_util.now()
        _LOGGER.debug("Now: %s Location: %r", now, self._location)

        today = now.date()
        sunset = dt_util.as_local(
            get_astral_event_date(self.hass, SUN_EVENT_SUNSET, today)
        )

        _LOGGER.debug("Now: %s Sunset: %s", now, sunset)

        daytime_date = hdate.HDate(today, diaspora=self._diaspora, hebrew=self._hebrew)

        # The Jewish day starts after darkness (called "tzais") and finishes at
        # sunset ("shkia"). The time in between is a gray area (aka "Bein
        # Hashmashot" - literally: "in between the sun and the moon").

        # For some sensors, it is more interesting to consider the date to be
        # tomorrow based on sunset ("shkia"), for others based on "tzais".
        # Hence the following variables.
        after_tzais_date = after_shkia_date = daytime_date
        today_times = self.make_zmanim(today)

        if now > sunset:
            after_shkia_date = daytime_date.next_day

        if today_times.havdalah and now > today_times.havdalah:
            after_tzais_date = daytime_date.next_day

        self._state = self.get_state(daytime_date, after_shkia_date, after_tzais_date)
        _LOGGER.debug("New value for %s: %s", self._type, self._state)

    def make_zmanim(self, date):
        """Create a Zmanim object."""
        return hdate.Zmanim(
            date=date,
            location=self._location,
            candle_lighting_offset=self._candle_lighting_offset,
            havdalah_offset=self._havdalah_offset,
            hebrew=self._hebrew,
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        if self._type != "holiday":
            return {}
        return self._holiday_attrs

    def get_state(self, daytime_date, after_shkia_date, after_tzais_date):
        """For a given type of sensor, return the state."""
        # Terminology note: by convention in py-libhdate library, "upcoming"
        # refers to "current" or "upcoming" dates.
        if self._type == "date":
            return after_shkia_date.hebrew_date
        if self._type == "weekly_portion":
            # Compute the weekly portion based on the upcoming shabbat.
            return after_tzais_date.upcoming_shabbat.parasha
        if self._type == "holiday":
            self._holiday_attrs["id"] = after_shkia_date.holiday_name
            self._holiday_attrs["type"] = after_shkia_date.holiday_type.name
            self._holiday_attrs["type_id"] = after_shkia_date.holiday_type.value
            return after_shkia_date.holiday_description
        if self._type == "omer_count":
            return after_shkia_date.omer_day
        if self._type == "daf_yomi":
            return daytime_date.daf_yomi

        return None


class JewishCalendarTimeSensor(JewishCalendarSensor):
    """Implement attrbutes for sensors returning times."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._state is None:
            return None
        return dt_util.as_utc(self._state).isoformat()

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        attrs: dict[str, str] = {}

        if self._state is None:
            return attrs

        return attrs

    def get_state(self, daytime_date, after_shkia_date, after_tzais_date):
        """For a given type of sensor, return the state."""
        if self._type == "upcoming_shabbat_candle_lighting":
            times = self.make_zmanim(
                after_tzais_date.upcoming_shabbat.previous_day.gdate
            )
            return times.candle_lighting
        if self._type == "upcoming_candle_lighting":
            times = self.make_zmanim(
                after_tzais_date.upcoming_shabbat_or_yom_tov.first_day.previous_day.gdate
            )
            return times.candle_lighting
        if self._type == "upcoming_shabbat_havdalah":
            times = self.make_zmanim(after_tzais_date.upcoming_shabbat.gdate)
            return times.havdalah
        if self._type == "upcoming_havdalah":
            times = self.make_zmanim(
                after_tzais_date.upcoming_shabbat_or_yom_tov.last_day.gdate
            )
            return times.havdalah

        times = self.make_zmanim(dt_util.now()).zmanim
        return times[self._type]
