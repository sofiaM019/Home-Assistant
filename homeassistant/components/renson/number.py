"""Platform to control a Renson ventilation unit."""
from __future__ import annotations

import logging

from renson_endura_delta.field_enum import FILTER_PRESET_FIELD, DataType
from renson_endura_delta.renson import RensonVentilation

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RensonCoordinator
from .const import DOMAIN
from .entity import RensonEntity

_LOGGER = logging.getLogger(__name__)


RENSON_NUMBER_DESCRIPTION = NumberEntityDescription(
    key="filter_change",
    name="Filter change",
    icon="mdi:filter",
    native_step=1,
    native_min_value=0,
    native_max_value=360,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renson number platform."""

    api: RensonVentilation = hass.data[DOMAIN][config_entry.entry_id].api
    coordinator: RensonCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ].coordinator

    async_add_entities([RensonNumber(RENSON_NUMBER_DESCRIPTION, api, coordinator)])


class RensonNumber(RensonEntity, NumberEntity):
    """Representation of the Renson number platform."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        description: NumberEntityDescription,
        api: RensonVentilation,
        coordinator: RensonCoordinator,
    ) -> None:
        """Initialize the Renson number."""
        super().__init__(description.key, api, coordinator)

        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.api.parse_value(
            self.api.get_field_value(self.coordinator.data, FILTER_PRESET_FIELD.name),
            DataType.NUMERIC,
        )

        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        _LOGGER.debug("Changing filter days to %s", value)

        await self.hass.async_add_executor_job(self.api.set_filter_days, value)
