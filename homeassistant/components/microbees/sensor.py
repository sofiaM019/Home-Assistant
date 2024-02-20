"""sensor integration microBees."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MicroBeesUpdateCoordinator
from .entity import MicroBeesEntity

SENSOR_TYPES = {
    0: SensorEntityDescription(
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        key="absorption",
        suggested_display_precision=2,
    ),
    2: SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        key="temperature",
        suggested_display_precision=1,
    ),
    14: SensorEntityDescription(
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        key="carbon_dioxide",
        suggested_display_precision=1,
    ),
    16: SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        key="humidity",
        suggested_display_precision=1,
    ),
    21: SensorEntityDescription(
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
        key="illuminance",
        suggested_display_precision=1,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    sensors = []
    for bee_id, bee in coordinator.data.bees.items():
        for sensor in bee.sensors:
            if sensor.device_type in (0, 2, 14, 16, 21):
                sensors.append(MBSensor(coordinator, bee_id, sensor.id))

    async_add_entities(sensors)


class MBSensor(MicroBeesEntity, SensorEntity):
    """Representation of a microBees sensor."""

    def __init__(
        self,
        coordinator: MicroBeesUpdateCoordinator,
        bee_id: int,
        sensor_id: int,
    ) -> None:
        """Initialize the microBees sensor."""
        super().__init__(coordinator, bee_id, None, sensor_id)
        self._attr_unique_id = f"sensor_{bee_id}_{sensor_id}"
        self.entity_description = SENSOR_TYPES.get(self.sensor.device_type)

    @property
    def name(self) -> str:
        """Name of the sensor."""
        return self.sensor.name

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the sensor, or None if the relevant sensor can't produce a current measurement."""
        return self.sensor.value
