"""Support for Jewish Calendar binary sensors."""
from __future__ import annotations

import datetime as dt

import hdate

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from . import DOMAIN

BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="issur_melacha_in_effect",
        name="Issur Melacha in Effect",
        icon="mdi:power-plug-off",
    ),
    BinarySensorEntityDescription(
        key="erev_shabbat_hag",
        name="Erev Shabbat/Hag",
    ),
    BinarySensorEntityDescription(
        key="motzei_shabbat_hag",
        name="Motzei Shabbat/Hag",
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Set up the Jewish Calendar binary sensor devices."""
    if discovery_info is None:
        return

    async_add_entities(
        [
            JewishCalendarBinarySensor(hass.data[DOMAIN], description)
            for description in BINARY_SENSORS
        ]
    )


class JewishCalendarBinarySensor(BinarySensorEntity):
    """Representation of an Jewish Calendar binary sensor."""

    _attr_should_poll = False

    def __init__(self, data, description: BinarySensorEntityDescription) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        self._attr_name = f"{data['name']} {description.name}"
        self._attr_unique_id = f"{data['prefix']}_{description.key}"
        self._location = data["location"]
        self._hebrew = data["language"] == "hebrew"
        self._candle_lighting_offset = data["candle_lighting_offset"]
        self._havdalah_offset = data["havdalah_offset"]
        self._update_unsub = None

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        zman = self._get_zmanim()
        if self.entity_description.key == "issur_melacha_in_effect":
            return zman.issur_melacha_in_effect
        if self.entity_description.key == "erev_shabbat_hag":
            return zman.erev_shabbat_hag
        if self.entity_description.key == "motzei_shabbat_hag":
            return zman.motzei_shabbat_hag

        return None

    def _get_zmanim(self):
        """Return the Zmanim object for now()."""
        return hdate.Zmanim(
            date=dt_util.now(),
            location=self._location,
            candle_lighting_offset=self._candle_lighting_offset,
            havdalah_offset=self._havdalah_offset,
            hebrew=self._hebrew,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._schedule_update()

    @callback
    def _update(self, now=None):
        """Update the state of the sensor."""
        self._update_unsub = None
        self._schedule_update()
        self.async_write_ha_state()

    def _schedule_update(self):
        """Schedule the next update of the sensor."""
        now = dt_util.now()
        zmanim = self._get_zmanim()
        update = zmanim.zmanim["sunrise"] + dt.timedelta(days=1)
        candle_lighting = zmanim.candle_lighting
        if candle_lighting is not None and now < candle_lighting < update:
            update = candle_lighting
        havdalah = zmanim.havdalah
        if havdalah is not None and now < havdalah < update:
            update = havdalah
        if self._update_unsub:
            self._update_unsub()
        self._update_unsub = event.async_track_point_in_time(
            self.hass, self._update, update
        )
