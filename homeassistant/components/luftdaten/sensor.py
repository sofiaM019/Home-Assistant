"""Support for Luftdaten sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONF_SHOW_ON_MAP,
    PERCENTAGE,
    PRESSURE_PA,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN
from .const import ATTR_SENSOR_ID, CONF_SENSOR_ID

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorEntityDescription(
        key="pressure",
        name="Pressure",
        icon="mdi:arrow-down-bold",
        native_unit_of_measurement=PRESSURE_PA,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    SensorEntityDescription(
        key="pressure_at_sealevel",
        name="Pressure at sealevel",
        icon="mdi:download",
        native_unit_of_measurement=PRESSURE_PA,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    SensorEntityDescription(
        key="P1",
        name="PM10",
        icon="mdi:thought-bubble",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    SensorEntityDescription(
        key="P2",
        name="PM2.5",
        icon="mdi:thought-bubble-outline",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Luftdaten sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        LuftdatenSensor(
            coordinator=coordinator,
            description=description,
            sensor_id=entry.data[CONF_SENSOR_ID],
            show_on_map=entry.data[CONF_SHOW_ON_MAP],
        )
        for description in SENSORS
        if description.key in coordinator.data
    )


class LuftdatenSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Luftdaten sensor."""

    _attr_attribution = "Data provided by luftdaten.info"
    _attr_should_poll = False

    def __init__(
        self,
        *,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
        sensor_id: int,
        show_on_map: bool,
    ) -> None:
        """Initialize the Luftdaten sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{sensor_id}_{description.key}"
        self._attr_extra_state_attributes = {
            ATTR_SENSOR_ID: sensor_id,
        }
        if show_on_map:
            self._attr_extra_state_attributes[ATTR_LONGITUDE] = coordinator.data[
                "longitude"
            ]
            self._attr_extra_state_attributes[ATTR_LATITUDE] = coordinator.data[
                "latitude"
            ]

    @property
    def native_value(self) -> float | None:
        """Return the state of the device."""
        if (
            not self.coordinator.data
            or (value := self.coordinator.data.get(self.entity_description.key)) is None
        ):
            return None
        return value
