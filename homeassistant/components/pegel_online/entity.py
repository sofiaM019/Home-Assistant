"""The pegel_online base entity."""
from __future__ import annotations

from aiopegelonline import Station

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .model import PegelOnlineData


class PegelOnlineEntity(CoordinatorEntity):
    """Representation of a pegel_online entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self, coordinator: DataUpdateCoordinator[PegelOnlineData], station: Station
    ) -> None:
        """Initialize a pegel_online entity."""
        super().__init__(coordinator)
        self.station = station
        self._attr_extra_state_attributes = {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.station.uuid)},
            name=f"{self.station.name} {self.station.water_name}",
            manufacturer=self.station.agency,
        )
