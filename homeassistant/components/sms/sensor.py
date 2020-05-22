"""Support for SMS dongle sensor."""
import logging

import gammu  # pylint: disable=import-error, no-member

from homeassistant.const import DEVICE_CLASS_SIGNAL_STRENGTH
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SMS_GATEWAY, SMS_GSM_SIGNAL_SENSOR_NAME

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the GSM Signal Sensor sensor."""
    name = SMS_GSM_SIGNAL_SENSOR_NAME
    gateway = hass.data[DOMAIN][SMS_GATEWAY]
    entities = []
    entities.append(GSMSignalSensor(hass, gateway, name,))
    async_add_entities(entities, True)


class GSMSignalSensor(Entity):
    """Implementation of a GSM Signal sensor."""

    def __init__(
        self, hass, gateway, name,
    ):
        """Initialize the GSM Signal sensor."""
        self._hass = hass
        self._gateway = gateway
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return "dB"

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEVICE_CLASS_SIGNAL_STRENGTH

    @property
    def available(self):
        """Return if the sensor data are available."""
        return self._state is not None

    @property
    def state(self):
        """Return the state of the device."""
        return self._state["SignalStrength"]

    @property
    async def async_force_update(self):
        """Force update."""
        try:
            self._state = await self._gateway.GetSignalQualityAsync()
        except gammu.GSMError as exc:  # pylint: disable=no-member
            _LOGGER.error("Failed to read signal quality: %s", exc)

    async def async_update(self):
        """Get the latest data from the modem."""
        try:
            self._state = await self._gateway.GetSignalQualityAsync()
        except gammu.GSMError as exc:  # pylint: disable=no-member
            _LOGGER.error("Failed to read signal quality: %s", exc)

    @property
    def device_state_attributes(self):
        """Return the sensor attributes."""
        return self._state
