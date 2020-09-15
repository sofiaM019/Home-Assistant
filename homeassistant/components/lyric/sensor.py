"""Support for Honeywell Lyric sensors."""
from datetime import datetime, timedelta
import logging
from typing import List

from aiolyric import Lyric
from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import LyricDeviceEntity
from .const import (
    DATA_COORDINATOR,
    DATA_LYRIC,
    DOMAIN,
    PRESET_HOLD_UNTIL,
    PRESET_NO_HOLD,
    PRESET_PERMANENT_HOLD,
    PRESET_TEMPORARY_HOLD,
    PRESET_VACATION_HOLD,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)
PARALLEL_UPDATES = 6


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Honeywell Lyric sensor platform based on a config entry."""
    lyric: Lyric = hass.data[DOMAIN][entry.entry_id][DATA_LYRIC]
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities = []

    locations: List[LyricLocation] = coordinator.data

    for location in locations:
        for device in location.devices:
            if device.indoorTemperature:
                entities.append(
                    LyricIndoorTemperatureSensor(
                        hass, lyric, coordinator, location, device
                    )
                )
            if device.outdoorTemperature:
                entities.append(
                    LyricOutdoorTemperatureSensor(
                        hass, lyric, coordinator, location, device
                    )
                )
            if device.displayedOutdoorHumidity:
                entities.append(
                    LyricOutdoorHumiditySensor(
                        hass, lyric, coordinator, location, device
                    )
                )
            if device.changeableValues:
                if device.changeableValues.nextPeriodTime:
                    entities.append(
                        LyricNextPeriodSensor(
                            hass, lyric, coordinator, location, device
                        )
                    )
                if device.changeableValues.thermostatSetpointStatus:
                    entities.append(
                        LyricSetpointStatusSensor(
                            hass, lyric, coordinator, location, device
                        )
                    )

    async_add_entities(entities, True)


class LyricSensor(LyricDeviceEntity):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        lyric: Lyric,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
        key: str,
        name: str,
        icon: str,
        device_class: str = None,
        unit_of_measurement: str = None,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement

        super().__init__(lyric, coordinator, location, device, key, name, icon)

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class LyricIndoorTemperatureSensor(LyricSensor):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        hass: HomeAssistantType,
        lyric: Lyric,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""

        super().__init__(
            lyric,
            coordinator,
            location,
            device,
            f"{device.macID}_indoor_temperature",
            "Indoor Temperature",
            "mdi:thermometer",
            DEVICE_CLASS_TEMPERATURE,
            hass.config.units.temperature_unit,
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        for location in self.coordinator.data:
            for device in location.devices:
                if device.macID == self._device.macID:
                    return device.indoorTemperature


class LyricOutdoorTemperatureSensor(LyricSensor):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        hass: HomeAssistantType,
        lyric: Lyric,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""

        super().__init__(
            lyric,
            coordinator,
            location,
            device,
            f"{device.macID}_outdoor_temperature",
            "Outdoor Temperature",
            "mdi:thermometer",
            DEVICE_CLASS_TEMPERATURE,
            hass.config.units.temperature_unit,
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        for location in self.coordinator.data:
            for device in location.devices:
                if device.macID == self._device.macID:
                    return device.outdoorTemperature


class LyricOutdoorHumiditySensor(LyricSensor):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        hass: HomeAssistantType,
        lyric: Lyric,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""

        super().__init__(
            lyric,
            coordinator,
            location,
            device,
            f"{device.macID}_outdoor_humidity",
            "Outdoor Humidity",
            "mdi:water-percent",
            DEVICE_CLASS_HUMIDITY,
            "%",
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        for location in self.coordinator.data:
            for device in location.devices:
                if device.macID == self._device.macID:
                    return device.displayedOutdoorHumidity


class LyricNextPeriodSensor(LyricSensor):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        hass: HomeAssistantType,
        lyric: Lyric,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""

        super().__init__(
            lyric,
            coordinator,
            location,
            device,
            f"{device.macID}_next_period_time",
            "Next Period Time",
            "mdi:clock",
            DEVICE_CLASS_TIMESTAMP,
        )

    @property
    def state(self) -> datetime:
        """Return the state of the sensor."""
        for location in self.coordinator.data:
            for device in location.devices:
                if device.macID == self._device.macID:
                    time = dt_util.parse_time(device.changeableValues.nextPeriodTime)
                    now = dt_util.utcnow()
                    if time <= now.time():
                        now = now + timedelta(days=1)
                    return dt_util.as_utc(datetime.combine(now.date(), time))


class LyricSetpointStatusSensor(LyricSensor):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        hass: HomeAssistantType,
        lyric: Lyric,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""

        super().__init__(
            lyric,
            coordinator,
            location,
            device,
            f"{device.macID}_setpoint_status",
            "Setpoint Status",
            "mdi:thermostat",
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        for location in self.coordinator.data:
            for device in location.devices:
                if device.macID == self._device.macID:
                    return (
                        "Following Schedule"
                        if device.changeableValues.thermostatSetpointStatus
                        == PRESET_NO_HOLD
                        else f"Held until {device.changeableValues.nextPeriodTime}"
                        if device.changeableValues.thermostatSetpointStatus
                        == PRESET_HOLD_UNTIL
                        else "Held Permanently"
                        if device.changeableValues.thermostatSetpointStatus
                        == PRESET_PERMANENT_HOLD
                        else "Held Temporarily"
                        if device.changeableValues.thermostatSetpointStatus
                        == PRESET_TEMPORARY_HOLD
                        else "Holiday"
                        if device.changeableValues.thermostatSetpointStatus
                        == PRESET_VACATION_HOLD
                        else "Unknown"
                    )
