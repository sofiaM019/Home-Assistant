"""Sensor platform for the Flipr's pool_sensor."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    TEMP_CELSIUS,
)

from . import FliprEntity
from .const import ATTRIBUTION, DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="chlorine",
        name="Chlorine",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
    ),
    SensorEntityDescription(
        key="ph",
        name="pH",
        icon="mdi:pool",
    ),
    SensorEntityDescription(
        key="temperature",
        name="Water Temp",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    SensorEntityDescription(
        key="date_time",
        name="Last Measured",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="red_ox",
        name="Red OX",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [FliprSensor(coordinator, description) for description in SENSOR_TYPES]
    async_add_entities(sensors, True)


class FliprSensor(FliprEntity, SensorEntity):
    """Sensor representing FliprSensor data."""

    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self):
        """Return the name of the particular component."""
        return f"Flipr {self.flipr_id} {self.entity_description.name}"

    @property
    def native_value(self):
        """State of the sensor."""
        state = self.coordinator.data[self.entity_description.key]
        if isinstance(state, datetime):
            return state.isoformat()
        return state

    @property
    def device_class(self):
        """Return the device class."""
        return self.entity_description.device_class

    @property
    def icon(self):
        """Return the icon."""
        return self.entity_description.icon

    @property
    def native_unit_of_measurement(self):
        """Return unit of measurement."""
        return self.entity_description.native_unit_of_measurement
