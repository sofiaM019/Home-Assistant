"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import asyncio
import logging
from typing import Union

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import SENSOR_TYPE_RAINDELAY, SENSOR_TYPE_RAINSENSOR
from .coordinator import RainbirdUpdateCoordinator

from .const import (
    DEVICE_INFO,
    DOMAIN,
    SENSOR_TYPE_RAINDELAY,
    SENSOR_TYPE_RAINSENSOR,
    SERIAL_NUMBER,
)

_LOGGER = logging.getLogger(__name__)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TYPE_RAINSENSOR,
        name="Rainsensor",
        icon="mdi:water",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_RAINDELAY,
        name="Raindelay",
        icon="mdi:water-off",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird sensor."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    await asyncio.gather(
        *[
            data[description.key].async_config_entry_first_refresh()
            for description in SENSOR_TYPES
        ],
    )
    async_add_devices(
        RainBirdSensor(
            data[description.key], description, data[SERIAL_NUMBER], data[DEVICE_INFO]
        )
        for description in SENSOR_TYPES
    )


class RainBirdSensor(
    CoordinatorEntity[RainbirdUpdateCoordinator[Union[int, bool]]], SensorEntity
):
    """A sensor implementation for Rain Bird device."""

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator[int | bool],
        description: SensorEntityDescription,
        serial_number: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{serial_number}-{description.key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data
