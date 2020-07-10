"""Platform for sensor integration."""
import logging
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util.distance import convert

from . import DOMAIN, NiuDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    vehicles = hass.data[DOMAIN][config.config_id].get_vehicles()

    for vehicle in vehicles:
        # TODO: take different models into account (single battery).
        add_entities(
            [
                NiuSensor(hass.data[DOMAIN][config.config_id], vehicle, "Level"),
                NiuSensor(hass.data[DOMAIN][config.config_id], vehicle, "Level A"),
                NiuSensor(hass.data[DOMAIN][config.config_id], vehicle, "Level B"),
                NiuSensor(hass.data[DOMAIN][config.config_id], vehicle, "Temp A"),
                NiuSensor(hass.data[DOMAIN][config.config_id], vehicle, "Temp B"),
            ],
            True,
        )


class NiuSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, account, vehicle, type=""):
        """Initialize the sensor."""
        self._account = account
        self._vehicle = vehicle
        self._type = type

        self._unit = None
        self._icon = None
        self._state = None

    @property
    def unique_id(self) -> str:
        return f"{self._vehicle.get_serial()}_{self._type}"

    @property
    def should_poll(self) -> bool:
        """Data update is centralized in NiuAccount"""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._vehicle.get_name()} {self._type}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self):
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_BATTERY_LEVEL: self._vehicle.get_soc(),
            ATTR_BATTERY_CHARGING: self._vehicle.is_charging(),
        }

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": (DOMAIN, self._vehicle.get_serial()),
            "name": self._vehicle.get_name(),
            "manufacturer": "NIU",
            "model": self._vehicle.get_model(),
        }

    def update_callback(self):
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Register state update callback."""

        self._account.add_update_listener(self.update_callback)

    def update(self) -> None:
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("Updating %s", self.name)

        if self._type == "Level":
            self._state = self._vehicle.get_soc()
        elif self._type == "Level A":
            self._state = self._vehicle.get_soc(0)
        elif self._type == "Level B":
            self._state = self._vehicle.get_soc(1)

        elif self._type == "Temp A":
            self._state = self._vehicle.get_battery_temp(0)
        elif self._type == "Temp B":
            self._state = self._vehicle.get_battery_temp(1)

        if "Level" in self._type:
            self._unit = "%"

            if self._state < 5:
                self._icon = "mdi:battery-outline"
            elif 5 <= self._state < 15:
                self._icon = "mdi:battery-10"
            elif 15 <= self._state < 25:
                self._icon = "mdi:battery-20"
            elif 25 <= self._state < 35:
                self._icon = "mdi:battery-30"
            elif 35 <= self._state < 45:
                self._icon = "mdi:battery-40"
            elif 45 <= self._state < 55:
                self._icon = "mdi:battery-50"
            elif 55 <= self._state < 65:
                self._icon = "mdi:battery-60"
            elif 65 <= self._state < 75:
                self._icon = "mdi:battery-70"
            elif 75 <= self._state < 85:
                self._icon = "mdi:battery-80"
            elif 85 <= self._state < 95:
                self._icon = "mdi:battery-90"
            elif self._state >= 95:
                self._icon = "mdi:battery"
            else:
                self._icon = "mdi:battery-alert"

        if "Temp" in self._type:
            self._unit = TEMP_CELSIUS

            if self._state < 15:
                self._icon = "mdi:thermometer-low"
            elif 15 <= self._state <= 40:
                self._icon = "mdi:thermometer"
            elif self._state >= 40:
                self._icon = "mdi:thermometer-high"
            else:
                self._icon = "mdi:thermometer-alert"
