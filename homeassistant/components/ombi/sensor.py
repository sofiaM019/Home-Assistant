"""Support for Ombi."""
from datetime import timedelta
import logging

from pyombi import OmbiError

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .const import DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ombi sensor platform."""
    if discovery_info is None:
        return

    ombi = hass.data[DOMAIN]["instance"]

    for sensor, sensor_val in SENSOR_TYPES.items():
        sensor_label = sensor
        sensor_type = sensor_val["type"]
        sensor_icon = sensor_val["icon"]
        sensors.append(OmbiSensor(sensor_label, sensor_type, ombi, sensor_icon))

    add_entities(entities, True)


class OmbiSensor(SensorEntity):
    """Representation of an Ombi sensor."""

    def __init__(self, ombi, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self._ombi = ombi

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update the sensor."""
        try:
            sensor_type = self.entity_description.key
            if sensor_type == "movies":
                self._attr_native_value = self._ombi.movie_requests
            elif sensor_type == "tv":
                self._attr_native_value = self._ombi.tv_requests
            elif sensor_type == "music":
                self._attr_native_value = self._ombi.music_requests
            elif sensor_type == "pending":
                self._attr_native_value = self._ombi.total_requests["pending"]
            elif sensor_type == "approved":
                self._attr_native_value = self._ombi.total_requests["approved"]
            elif sensor_type == "available":
                self._attr_native_value = self._ombi.total_requests["available"]
        except OmbiError as err:
            _LOGGER.warning("Unable to update Ombi sensor: %s", err)
            self._attr_native_value = None
