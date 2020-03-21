"""Support for Lutron Caseta Occupancy/Vacancy Sensors."""
from pylutron_caseta import OCCUPANCY_GROUP_OCCUPIED

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OCCUPANCY,
    BinarySensorDevice,
)

from . import LUTRON_CASETA_SMARTBRIDGE, LutronCasetaDevice


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Lutron Caseta lights."""
    entities = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    occupancy_groups = bridge.occupancy_groups
    for occupancy_group in occupancy_groups.values():
        entity = LutronOccupancySensor(occupancy_group, bridge)
        entities.append(entity)

    async_add_entities(entities, True)


class LutronOccupancySensor(LutronCasetaDevice, BinarySensorDevice):
    """Representation of a Lutron occupancy group."""

    @property
    def device_class(self):
        """Flag supported features."""
        return DEVICE_CLASS_OCCUPANCY

    @property
    def is_on(self):
        """Return the brightness of the light."""
        return self._device["status"] == OCCUPANCY_GROUP_OCCUPIED

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._smartbridge.add_occupancy_subscriber(
            self.device_id, self.async_write_ha_state
        )

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["occupancy_group_id"]

    @property
    def unique_id(self):
        """Return a unique identifier."""
        return f"caseta_occupancygroup_{self.device_id}"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"device_id": self.device_id}
