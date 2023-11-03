"""Sensor for retrieving data for SEMS portal."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CURRENCY_DOLLAR,
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, SemsDataUpdateCoordinator


class SemsSensor(SensorEntity):
    """Used to represent a SemsSensor."""

    _attr_has_entity_name = True

    entity_description: SensorEntityDescription

    def __init__(
        self,
        device: Any,
        config_entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        deviceName = device["name"]
        deviceModel = device["model"]
        self.device = device
        self._config_entry_id = config_entry.entry_id
        self.entity_description = description
        self._attr_unique_id = f"{deviceName}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, deviceName)},
            manufacturer="Goodwe",
            model=deviceModel,
            name=deviceName,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        sensor_type = self.entity_description.key
        return self.device[sensor_type]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Get the setup sensor."""

    coordinator: SemsDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    interters = coordinator.data["powerPlant"]["inverters"]
    powerPlantInformation = coordinator.data["powerPlant"]["info"]

    inverterEntities = [
        SemsSensor(device, config_entry, description)
        for description in SENSOR_TYPES_INVERTERS
        for device in interters
    ]

    powerPlantInformationEntities = [
        SemsSensor(powerPlantInformation, config_entry, description)
        for description in SENSOR_TYPES_POWERSTATION
    ]

    inverterEntities += powerPlantInformationEntities

    async_add_entities(inverterEntities)


SENSOR_TYPES_INVERTERS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        name="Inner Temp",
        key="innerTemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
)

SENSOR_TYPES_POWERSTATION: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        name="Powerstation Id",
        key="powerstation_id",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="Station Name",
        key="stationname",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="Battery Capacity",
        key="battery_capacity",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Capacity",
        key="capacity",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Month Generation",
        key="monthGeneration",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Generation Live",
        key="generationLive",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Generation Today",
        key="generationToday",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="All Time Generation",
        key="allTimeGeneration",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Today Income",
        key="todayIncome",
        native_unit_of_measurement=CURRENCY_DOLLAR,
        device_class=SensorDeviceClass.MONETARY,
    ),
    SensorEntityDescription(
        name="Total Income",
        key="totalIncome",
        native_unit_of_measurement=CURRENCY_DOLLAR,
        device_class=SensorDeviceClass.MONETARY,
    ),
    SensorEntityDescription(
        name="Battery",
        key="battery",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Battery Status",
        key="batteryStatus",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="Battery Status Str",
        key="batteryStatusStr",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="House Load",
        key="houseLoad",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="House Load Status",
        key="houseLoadStatus",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="Grid Load",
        key="gridLoad",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Grid Load Status",
        key="gridLoadStatus",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="Soc", key="soc", native_unit_of_measurement=None, device_class=None
    ),
    SensorEntityDescription(
        name="Soc Text",
        key="socText",
        native_unit_of_measurement=PERCENTAGE,
        device_class=None,
    ),
)
