"""Support for Soma sensors."""
from datetime import timedelta
import logging

from requests import RequestException

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from . import DEVICES, SomaEntity
from .const import API, DOMAIN
from .utils import is_api_response_success

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Soma sensor platform."""

    devices = hass.data[DOMAIN][DEVICES]

    async_add_entities(
        [SomaSensor(sensor, hass.data[DOMAIN][API]) for sensor in devices], True
    )


class SomaSensor(SomaEntity, SensorEntity):
    """Representation of a Soma cover device."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def name(self):
        """Return the name of the device."""
        return self.device["name"] + " battery level"

    @property
    def native_value(self):
        """Return the state of the entity."""
        return self.battery_state

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update the sensor with the latest data."""
        try:
            _LOGGER.debug("Soma Sensor Update")
            response = await self.hass.async_add_executor_job(
                self.api.get_battery_level, self.device["mac"]
            )
            if not self.api_is_available:
                self.api_is_available = True
                _LOGGER.info("Connection to SOMA Connect succeeded")
        except RequestException:
            if self.api_is_available:
                _LOGGER.warning("Connection to SOMA Connect failed")
                self.api_is_available = False
            return
        if not is_api_response_success(response):
            if self.is_available:
                self.is_available = False
                _LOGGER.warning(
                    "Device is unreachable (%s). Error while fetching the battery state: %s",
                    self.name,
                    response["msg"],
                )
            return

        if not self.is_available:
            self.is_available = True
            _LOGGER.info("Device %s is now reachable", self.name)

        # https://support.somasmarthome.com/hc/en-us/articles/360026064234-HTTP-API
        # battery_level response is expected to be min = 360, max 410 for
        # 0-100% levels above 410 are consider 100% and below 360, 0% as the
        # device considers 360 the minimum to move the motor.
        _battery = round(2 * (response["battery_level"] - 360))
        battery = max(min(100, _battery), 0)
        self.battery_state = battery
