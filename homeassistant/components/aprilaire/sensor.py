"""The Aprilaire sensor component."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from pyaprilaire.const import Attribute

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import AprilaireCoordinator
from .entity import BaseAprilaireEntity

DEHUMIDIFICATION_STATUS_MAP = {
    0: "idle",
    1: "idle",
    2: "on",
    3: "on",
    4: "off",
}

HUMIDIFICATION_STATUS_MAP = {
    0: "idle",
    1: "idle",
    2: "on",
    3: "off",
}

VENTILATION_STATUS_MAP = {
    0: "idle",
    1: "idle",
    2: "on",
    3: "idle",
    4: "idle",
    5: "idle",
    6: "off",
}

AIR_CLEANING_STATUS_MAP = {
    0: "idle",
    1: "idle",
    2: "on",
    3: "off",
}

FAN_STATUS_MAP = {0: "off", 1: "on"}


@dataclass(frozen=True, kw_only=True)
class AprilaireSensorDescription(SensorEntityDescription):
    """Class describing Aprilaire sensor entities."""

    status_key: str | None
    status_sensor_available_value: int | None
    status_sensor_exists_values: list[int] | None
    value_key: str
    value_fn: Callable[[Any, Any], StateType] | None


SENSOR_TYPES: tuple[AprilaireSensorDescription, ...] = (
    AprilaireSensorDescription(
        key="indoor_humidity_controlling_sensor",
        translation_key="indoor_humidity_controlling_sensor",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        status_key=Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_STATUS,
        status_sensor_available_value=0,
        status_sensor_exists_values=[0, 1, 2],
        value_key=Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_VALUE,
        value_fn=None,
    ),
    AprilaireSensorDescription(
        key="outdoor_humidity_controlling_sensor",
        translation_key="outdoor_humidity_controlling_sensor",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        status_key=Attribute.OUTDOOR_HUMIDITY_CONTROLLING_SENSOR_STATUS,
        status_sensor_available_value=0,
        status_sensor_exists_values=[0, 1, 2],
        value_key=Attribute.OUTDOOR_HUMIDITY_CONTROLLING_SENSOR_VALUE,
        value_fn=None,
    ),
    AprilaireSensorDescription(
        key="indoor_temperature_controlling_sensor",
        translation_key="indoor_temperature_controlling_sensor",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        status_key=Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS,
        status_sensor_available_value=0,
        status_sensor_exists_values=[0, 1, 2],
        value_key=Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_VALUE,
        value_fn=None,
    ),
    AprilaireSensorDescription(
        key="outdoor_temperature_controlling_sensor",
        translation_key="outdoor_temperature_controlling_sensor",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        status_key=Attribute.OUTDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS,
        status_sensor_available_value=0,
        status_sensor_exists_values=[0, 1, 2],
        value_key=Attribute.OUTDOOR_TEMPERATURE_CONTROLLING_SENSOR_VALUE,
        value_fn=None,
    ),
    AprilaireSensorDescription(
        key="dehumidification_status",
        translation_key="dehumidification_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(set(DEHUMIDIFICATION_STATUS_MAP.values())),
        status_key=Attribute.DEHUMIDIFICATION_AVAILABLE,
        status_sensor_available_value=None,
        status_sensor_exists_values=[1],
        value_key=Attribute.DEHUMIDIFICATION_STATUS,
        value_fn=lambda _, value: DEHUMIDIFICATION_STATUS_MAP.get(value),
    ),
    AprilaireSensorDescription(
        key="humidification_status",
        translation_key="humidification_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(set(HUMIDIFICATION_STATUS_MAP.values())),
        status_key=Attribute.HUMIDIFICATION_AVAILABLE,
        status_sensor_available_value=None,
        status_sensor_exists_values=[1, 2],
        value_key=Attribute.HUMIDIFICATION_STATUS,
        value_fn=lambda _, value: HUMIDIFICATION_STATUS_MAP.get(value),
    ),
    AprilaireSensorDescription(
        key="ventilation_status",
        translation_key="ventilation_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(set(VENTILATION_STATUS_MAP.values())),
        status_key=Attribute.VENTILATION_AVAILABLE,
        status_sensor_available_value=None,
        status_sensor_exists_values=[1],
        value_key=Attribute.VENTILATION_STATUS,
        value_fn=lambda _, value: VENTILATION_STATUS_MAP.get(value),
    ),
    AprilaireSensorDescription(
        key="air_cleaning_status",
        translation_key="air_cleaning_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(set(AIR_CLEANING_STATUS_MAP.values())),
        status_key=Attribute.AIR_CLEANING_AVAILABLE,
        status_sensor_available_value=None,
        status_sensor_exists_values=[1],
        value_key=Attribute.AIR_CLEANING_STATUS,
        value_fn=lambda _, value: AIR_CLEANING_STATUS_MAP.get(value),
    ),
    AprilaireSensorDescription(
        key="fan_status",
        translation_key="fan_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(set(FAN_STATUS_MAP.values())),
        status_key=None,
        status_sensor_available_value=None,
        status_sensor_exists_values=[],
        value_key=Attribute.FAN_STATUS,
        value_fn=lambda _, value: FAN_STATUS_MAP.get(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aprilaire sensor devices."""

    coordinator: AprilaireCoordinator = hass.data[DOMAIN][config_entry.unique_id]

    assert config_entry.unique_id is not None

    async_add_entities(
        AprilaireSensor(coordinator, description, config_entry.unique_id)
        for description in SENSOR_TYPES
        if description.status_key is None
        or description.status_sensor_exists_values is None
        or coordinator.data.get(description.status_key)
        in description.status_sensor_exists_values
    )


class AprilaireSensor(BaseAprilaireEntity, SensorEntity):
    """Sensor entity for Aprilaire."""

    entity_description: AprilaireSensorDescription

    def __init__(
        self,
        coordinator: AprilaireCoordinator,
        description: AprilaireSensorDescription,
        unique_id: str,
    ) -> None:
        """Initialize a sensor for an Aprilaire device."""

        self.entity_description = description

        super().__init__(coordinator, unique_id)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if (
            self.entity_description.status_key is None
            or self.entity_description.status_sensor_available_value is None
        ):
            return True

        if not super().available:
            return False

        return (
            self.coordinator.data.get(self.entity_description.status_key)
            == self.entity_description.status_sensor_available_value
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        raw_value = self.coordinator.data.get(self.entity_description.value_key)

        if self.entity_description.value_fn is None:
            # Valid cast as pyaprilaire only provides str | int | float
            return cast(StateType, raw_value)

        return self.entity_description.value_fn(self, raw_value)
