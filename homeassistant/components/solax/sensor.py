"""Support for Solax inverter via local API."""
from __future__ import annotations

import asyncio
from datetime import timedelta

from solax import RealTimeAPI
from solax.discovery import InverterError
from solax.units import Total, Units

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, MANUFACTURER

DEFAULT_PORT = 80
SCAN_INTERVAL = timedelta(seconds=30)


DEVICE_CLASS_MAPPING = {
    Units.C: SensorDeviceClass.TEMPERATURE,
    Units.KWH: SensorDeviceClass.ENERGY,
    Units.V: SensorDeviceClass.VOLTAGE,
    Units.A: SensorDeviceClass.CURRENT,
    Units.W: SensorDeviceClass.POWER,
    Units.PERCENT: SensorDeviceClass.BATTERY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Entry setup."""
    api: RealTimeAPI = hass.data[DOMAIN][entry.entry_id]
    resp = await api.get_data()
    serial = resp.serial_number
    version = resp.version
    endpoint = RealTimeDataEndpoint(hass, api)
    hass.async_add_job(endpoint.async_refresh)
    async_track_time_interval(hass, endpoint.async_refresh, SCAN_INTERVAL)
    devices = []
    for sensor, (idx, measurement) in api.inverter.sensor_map().items():
        state_class = None
        device_class = DEVICE_CLASS_MAPPING.get(measurement.unit, None)
        if device_class:
            if measurement.is_monotonic:
                state_class = SensorStateClass.TOTAL_INCREASING
            else:
                state_class = SensorStateClass.MEASUREMENT
        unit = measurement.unit.value

        uid = f"{serial}-{idx}"
        devices.append(
            Inverter(
                api.inverter.manufacturer,
                uid,
                serial,
                version,
                sensor,
                unit,
                state_class,
                device_class,
            )
        )
    endpoint.sensors = devices
    async_add_entities(devices)


class RealTimeDataEndpoint:
    """Representation of a Sensor."""

    def __init__(self, hass: HomeAssistant, api: RealTimeAPI) -> None:
        """Initialize the sensor."""
        self.hass: HomeAssistant = hass
        self.api = api
        self.ready = asyncio.Event()
        self.sensors: list[Inverter] = []

    async def async_refresh(self, now=None):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            api_response = await self.api.get_data()
            self.ready.set()
        except InverterError as err:
            if now is not None:
                self.ready.clear()
                return
            raise PlatformNotReady from err
        data = api_response.data
        for sensor in self.sensors:
            if sensor.key in data:
                sensor.value = data[sensor.key]
                sensor.async_schedule_update_ha_state()


class Inverter(SensorEntity):
    """Class for a sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        manufacturer,
        uid,
        serial,
        version,
        key,
        unit,
        state_class=None,
        device_class=None,
    ):
        """Initialize an inverter sensor."""
        self._attr_unique_id = uid
        self._attr_name = f"{manufacturer} {serial} {key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=MANUFACTURER,
            name=f"{manufacturer} {serial}",
            sw_version=version,
        )
        self.key = key
        self.value = None

    @property
    def native_value(self):
        """State of this inverter attribute."""
        return self.value
