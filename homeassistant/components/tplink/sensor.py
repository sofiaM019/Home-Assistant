"""Support for TPLink HS100/HS110/HS200 smart switch energy sensors."""
from __future__ import annotations

from typing import Final, cast

from kasa import SmartDevice

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_VOLTAGE,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import legacy_device_id
from .const import (
    ATTR_CURRENT_A,
    ATTR_CURRENT_POWER_W,
    ATTR_TODAY_ENERGY_KWH,
    ATTR_TOTAL_ENERGY_KWH,
    DOMAIN,
)
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity

ENERGY_SENSORS: Final[list[SensorEntityDescription]] = [
    SensorEntityDescription(
        key=ATTR_CURRENT_POWER_W,
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Current Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_KWH,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        name="Total Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_TODAY_ENERGY_KWH,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        name="Today's Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_VOLTAGE,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Voltage",
    ),
    SensorEntityDescription(
        key=ATTR_CURRENT_A,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Current",
    ),
]

KEY_TO_PROPERTY_MAP = {
    ATTR_CURRENT_POWER_W: "power",
    ATTR_TOTAL_ENERGY_KWH: "total",
    ATTR_VOLTAGE: "voltage",
    ATTR_CURRENT_A: "current",
}


def async_get_key_value_from_device(device: SmartDevice, key: str) -> float | None:
    """Map a sensor key to the device attribute."""
    if attr := KEY_TO_PROPERTY_MAP.get(key):
        val = getattr(device.emeter_realtime, attr)
        if val is None:
            return None
        return cast(float, val)

    # ATTR_TODAY_ENERGY_KWH
    if (emeter_today := device.emeter_today) is not None:
        return cast(float, emeter_today)
    # today's consumption not available, when device was off all the day
    # bulb's do not report this information, so filter it out
    return None if device.is_bulb else 0.0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: TPLinkDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[SmartPlugSensor] = []
    parent = coordinator.device
    if not parent.has_emeter:
        return

    def _async_sensors_for_device(device: SmartDevice) -> list[SmartPlugSensor]:
        return [
            SmartPlugSensor(device, coordinator, description)
            for description in ENERGY_SENSORS
            if async_get_key_value_from_device(device, description.key) is not None
        ]

    if parent.is_strip:
        # Historiclly we only add the children if the device is a strip
        for child in parent.children:
            entities.extend(_async_sensors_for_device(child))
    else:
        entities.extend(_async_sensors_for_device(parent))

    async_add_entities(entities)


class SmartPlugSensor(CoordinatedTPLinkEntity, SensorEntity):
    """Representation of a TPLink Smart Plug energy sensor."""

    coordinator: TPLinkDataUpdateCoordinator

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{legacy_device_id(self.device)}_{self.entity_description.key}"
        )

    @property
    def name(self) -> str:
        """Return the name of the Smart Plug.

        Overridden to include the description.
        """
        return f"{self.device.alias} {self.entity_description.name}"

    @property
    def native_value(self) -> float | None:
        """Return the sensors state."""
        return async_get_key_value_from_device(self.device, self.entity_description.key)
