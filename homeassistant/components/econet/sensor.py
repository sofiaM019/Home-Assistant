"""Support for Rheem EcoNet water heaters."""
from pyeconet.equipment import EquipmentType

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcoNetEntity
from .const import DOMAIN, EQUIPMENT

ENERGY_KILO_BRITISH_THERMAL_UNIT = "kBtu"

TANK_HEALTH = "tank_health"
AVAILABLE_HOT_WATER = "available_hot_water"
COMPRESSOR_HEALTH = "compressor_health"
OVERRIDE_STATUS = "override_status"
WATER_USAGE_TODAY = "water_usage_today"
POWER_USAGE_TODAY = "power_usage_today"
ALERT_COUNT = "alert_count"
WIFI_SIGNAL = "wifi_signal"
RUNNING_STATE = "running_state"

SENSOR_NAMES_TO_ATTRIBUTES = {
    TANK_HEALTH: "tank_health",
    AVAILABLE_HOT_WATER: "tank_hot_water_availability",
    COMPRESSOR_HEALTH: "compressor_health",
    OVERRIDE_STATUS: "override_status",
    WATER_USAGE_TODAY: "todays_water_usage",
    POWER_USAGE_TODAY: "todays_energy_usage",
    ALERT_COUNT: "alert_count",
    WIFI_SIGNAL: "wifi_signal",
    RUNNING_STATE: "running_state",
}

SENSOR_NAMES_TO_UNIT_OF_MEASUREMENT = {
    TANK_HEALTH: PERCENTAGE,
    AVAILABLE_HOT_WATER: PERCENTAGE,
    COMPRESSOR_HEALTH: PERCENTAGE,
    OVERRIDE_STATUS: None,
    WATER_USAGE_TODAY: UnitOfVolume.GALLONS,
    POWER_USAGE_TODAY: None,  # Depends on unit type
    ALERT_COUNT: None,
    WIFI_SIGNAL: SIGNAL_STRENGTH_DECIBELS,
    RUNNING_STATE: None,  # This is just a string
}

SENSOR_NAMES_TO_STATE_CLASS = {
    TANK_HEALTH: SensorStateClass.MEASUREMENT,
    AVAILABLE_HOT_WATER: SensorStateClass.MEASUREMENT,
    COMPRESSOR_HEALTH: SensorStateClass.MEASUREMENT,
    OVERRIDE_STATUS: None,
    WATER_USAGE_TODAY: SensorStateClass.TOTAL_INCREASING,
    POWER_USAGE_TODAY: SensorStateClass.TOTAL_INCREASING,
    ALERT_COUNT: None,
    WIFI_SIGNAL: SensorStateClass.MEASUREMENT,
    RUNNING_STATE: None,
}

SENSOR_NAMES_TO_DEVICE_CLASS = {
    TANK_HEALTH: None,
    AVAILABLE_HOT_WATER: None,
    COMPRESSOR_HEALTH: None,
    OVERRIDE_STATUS: None,
    WATER_USAGE_TODAY: SensorDeviceClass.WATER,
    POWER_USAGE_TODAY: SensorDeviceClass.ENERGY,
    ALERT_COUNT: None,
    WIFI_SIGNAL: SensorDeviceClass.SIGNAL_STRENGTH,
    RUNNING_STATE: None,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EcoNet sensor based on a config entry."""

    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    sensors = []
    all_equipment = equipment[EquipmentType.WATER_HEATER].copy()
    all_equipment.extend(equipment[EquipmentType.THERMOSTAT].copy())

    for _equip in all_equipment:
        for name, attribute in SENSOR_NAMES_TO_ATTRIBUTES.items():
            if getattr(_equip, attribute, None) is not None:
                sensors.append(EcoNetSensor(_equip, name))
        # This is None to start with and all device have it
        sensors.append(EcoNetSensor(_equip, WIFI_SIGNAL))

    for water_heater in equipment[EquipmentType.WATER_HEATER]:
        # These aren't part of the device and start off as None in pyeconet so always add them
        sensors.append(EcoNetSensor(water_heater, WATER_USAGE_TODAY))
        sensors.append(EcoNetSensor(water_heater, POWER_USAGE_TODAY))

    async_add_entities(sensors)


class EcoNetSensor(EcoNetEntity, SensorEntity):
    """Define a Econet sensor."""

    def __init__(self, econet_device, device_name):
        """Initialize."""
        super().__init__(econet_device)
        self._econet = econet_device
        self._device_name = device_name

    @property
    def native_value(self):
        """Return sensors state."""
        value = getattr(self._econet, SENSOR_NAMES_TO_ATTRIBUTES[self._device_name])
        if isinstance(value, float):
            value = round(value, 2)
        return value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        unit_of_measurement = SENSOR_NAMES_TO_UNIT_OF_MEASUREMENT[self._device_name]
        if self._device_name == POWER_USAGE_TODAY:
            if self._econet.energy_type == ENERGY_KILO_BRITISH_THERMAL_UNIT.upper():
                unit_of_measurement = ENERGY_KILO_BRITISH_THERMAL_UNIT
            else:
                unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        return unit_of_measurement

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self._econet.device_name}_{self._device_name}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return (
            f"{self._econet.device_id}_{self._econet.device_name}_{self._device_name}"
        )
    
    @property
    def state_class(self):
        '''Return the state class'''
        return SENSOR_NAMES_TO_STATE_CLASS[self._device_name]
    
    @property
    def device_class(self):
        '''Return the device class'''
        return SENSOR_NAMES_TO_DEVICE_CLASS[self._device_name]
