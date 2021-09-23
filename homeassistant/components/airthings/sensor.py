"""Support for Airthings sensors."""
from __future__ import annotations

from dataclasses import dataclass

from airthings import AirthingsDevice

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
    PERCENTAGE,
    PRESSURE_MBAR,
    TEMP_CELSIUS,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


@dataclass
class AirthingsSensorEntityDescription(SensorEntityDescription):
    """Describes Airthings sensor entity."""

    sensor_name: str | None = None


SENSORS: dict[str, AirthingsSensorEntityDescription] = {
    "radonShortTermAvg": AirthingsSensorEntityDescription(
        key="radonShortTermAvg",
        native_unit_of_measurement="Bq/m³",
        sensor_name="Radon",
    ),
    "temp": AirthingsSensorEntityDescription(
        key="temp",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        sensor_name="Temperature",
    ),
    "humidity": AirthingsSensorEntityDescription(
        key="humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        sensor_name="Humidity",
    ),
    "pressure": AirthingsSensorEntityDescription(
        key="pressure",
        device_class=DEVICE_CLASS_PRESSURE,
        native_unit_of_measurement=PRESSURE_MBAR,
        sensor_name="Pressure",
    ),
    "battery": AirthingsSensorEntityDescription(
        key="battery",
        device_class=DEVICE_CLASS_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        sensor_name="Battery",
    ),
    "co2": AirthingsSensorEntityDescription(
        key="co2",
        device_class=DEVICE_CLASS_CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        sensor_name="CO2",
    ),
    "voc": AirthingsSensorEntityDescription(
        key="voc",
        device_class=DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        sensor_name="VOC",
    ),
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Airthings sensor."""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AirthingsHeaterEnergySensor(
            coordinator,
            airthings_device,
            SENSORS[sensor_types],
        )
        for airthings_device in coordinator.data.values()
        for sensor_types in airthings_device.sensor_types
        if sensor_types in SENSORS
    ]
    async_add_entities(entities)


class AirthingsHeaterEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Airthings Sensor device."""

    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        airthings_device: AirthingsDevice,
        entity_description: AirthingsSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description

        self._attr_name = f"{airthings_device.name} {entity_description.sensor_name}"
        self._attr_unique_id = f"{airthings_device.device_id}_{entity_description.key}"
        self._id = airthings_device.device_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, airthings_device.device_id)},
            "name": self.name,
            "manufacturer": "Airthings",
        }

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data[self._id].sensors[self.entity_description.key]
