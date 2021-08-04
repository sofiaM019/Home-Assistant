"""Support for Velbus sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DEVICE_CLASS_POWER, ENERGY_KILO_WATT_HOUR

from . import VelbusEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus switch based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for channel in cntrl.get_all("sensor"):
        entities.append(VelbusSensor(channel))
        if channel.get_class() == "counter":
            entities.append(VelbusSensor(channel, True))
    async_add_entities(entities)


class VelbusSensor(VelbusEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(self, channel, counter=False):
        """Initialize a sensor Velbus entity."""
        super().__init__(channel)
        self._is_counter = counter

    @property
    def unique_id(self):
        """Return unique ID for counter sensors."""
        unique_id = super().unique_id
        if self._is_counter:
            unique_id = f"{unique_id}-counter"
        return unique_id

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self._channel.get_class() == "counter" and not self._is_counter:
            if self._channel.get_unit() == ENERGY_KILO_WATT_HOUR:
                return DEVICE_CLASS_POWER
            return None
        return self._channel.get_class()

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._is_counter:
            return self._channel.get_counter_state()
        return self._channel.get_state()

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._channel.get_unit()

    @property
    def icon(self):
        """Icon to use in the frontend."""
        if self._is_counter:
            return "mdi:counter"
        return None
