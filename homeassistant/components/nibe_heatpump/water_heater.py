"""The Nibe Heat Pump sensors."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from nibe.coil import Coil
from nibe.coil_groups import (
    UNIT_COILGROUPS,
    WATER_HEATER_COILGROUPS,
    UnitCoilGroup,
    WaterHeaterCoilGroup,
)
from nibe.exceptions import CoilNotFoundException

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, LOGGER, Coordinator
from .const import VALUES_PRIORITY_HOT_WATER, VALUES_TEMPORARY_LUX_INACTIVE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    main_unit = UNIT_COILGROUPS.get(coordinator.series, {}).get("main")
    if not main_unit:
        LOGGER.debug("Skipping water_heaters - no main unit found")
        return

    def water_heaters():
        for key, group in WATER_HEATER_COILGROUPS.get(coordinator.series, ()).items():
            try:
                yield WaterHeater(coordinator, key, main_unit, group)
            except CoilNotFoundException as exception:
                LOGGER.debug("Skipping water heater: %r", exception)

    async_add_entities(water_heaters())


class WaterHeaterEntityFixed(WaterHeaterEntity):
    """Base class to disentangle the configuration of operation mode from the state."""

    _attr_operation_mode: str | None

    @property
    def operation_mode(self) -> str | None:
        """Return the operation modes currently configured."""
        if hasattr(self, "_attr_operation_mode"):
            return self._attr_operation_mode
        return self.current_operation

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes."""
        data: dict[str, Any] = {}
        if (operation_mode := self.operation_mode) is not None:
            data[ATTR_OPERATION_MODE] = operation_mode

        return data


class WaterHeater(CoordinatorEntity[Coordinator], WaterHeaterEntityFixed):
    """Sensor entity."""

    _attr_entity_category = None
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE
    _attr_max_temp = 35.0
    _attr_min_temp = 5.0

    def __init__(
        self,
        coordinator: Coordinator,
        key: str,
        unit: UnitCoilGroup,
        desc: WaterHeaterCoilGroup,
    ) -> None:
        """Initialize entity."""

        super().__init__(
            coordinator,
            {
                desc.hot_water_load,
                desc.hot_water_comfort_mode,
                *set(desc.start_temperature.values()),
                *set(desc.stop_temperature.values()),
                unit.prio,
                desc.active_accessory,
                desc.temporary_lux,
            },
        )
        self._attr_entity_registry_enabled_default = desc.active_accessory is None
        self._attr_available = False
        self._attr_name = desc.name
        self._attr_unique_id = f"{coordinator.unique_id}-{key}"
        self._attr_device_info = coordinator.device_info

        self._attr_current_operation = None
        self._attr_operation_mode = None
        self._attr_target_temperature_high = None
        self._attr_target_temperature_low = None
        self._attr_operation_list = [STATE_HEAT_PUMP]

        def _get(address: int) -> Coil:
            return coordinator.heatpump.get_coil_by_address(address)

        def _map(data: dict[str, int]) -> dict[str, Coil]:
            return {key: _get(address) for key, address in data.items()}

        self._coil_current = _get(desc.hot_water_load)
        self._coil_start_temperature = _map(desc.start_temperature)
        self._coil_stop_temperature = _map(desc.stop_temperature)
        self._coil_prio = _get(unit.prio)
        self._coil_temporary_lux: Coil | None = None
        if desc.temporary_lux:
            self._coil_temporary_lux = _get(desc.temporary_lux)
        self._coil_active_accessory: Coil | None = None
        if address := desc.active_accessory:
            self._coil_active_accessory = _get(address)

        self._coil_hot_water_comfort_mode = _get(desc.hot_water_comfort_mode)

        if self._coil_temporary_lux:
            self._attr_operation_list.append(STATE_HIGH_DEMAND)

        self._attr_temperature_unit = self._coil_current.unit

    def _handle_coordinator_update(self) -> None:
        if not self.coordinator.data:
            return

        def _get_float(coil: Coil | None) -> float | None:
            if coil is None:
                return None
            return self.coordinator.get_coil_float(coil)

        def _get_value(coil: Coil | None) -> int | str | float | None:
            if coil is None:
                return None
            return self.coordinator.get_coil_value(coil)

        self._attr_current_temperature = _get_float(self._coil_current)

        if (mode := _get_value(self._coil_hot_water_comfort_mode)) and isinstance(
            mode, str
        ):
            self._attr_target_temperature_low = _get_float(
                self._coil_start_temperature.get(mode)
            )
            self._attr_target_temperature_high = _get_float(
                self._coil_stop_temperature.get(mode)
            )
        else:
            self._attr_target_temperature_low = None
            self._attr_target_temperature_high = None

        if (
            mode := _get_value(self._coil_temporary_lux)
        ) is None or mode in VALUES_TEMPORARY_LUX_INACTIVE:
            self._attr_operation_mode = STATE_HEAT_PUMP
        else:
            self._attr_operation_mode = STATE_HIGH_DEMAND

        if prio := _get_value(self._coil_prio):
            if prio in VALUES_PRIORITY_HOT_WATER:
                self._attr_current_operation = STATE_HEAT_PUMP
            else:
                self._attr_current_operation = STATE_OFF
        else:
            self._attr_current_operation = None

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        if not self._coil_active_accessory:
            return True

        if active_accessory := self.coordinator.get_coil_value(
            self._coil_active_accessory
        ):
            return active_accessory == "ON"

        return False

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        if not self._coil_temporary_lux:
            raise HomeAssistantError("Not supported")

        if operation_mode == STATE_HEAT_PUMP:
            await self.coordinator.async_write_coil(self._coil_temporary_lux, "OFF")
        elif operation_mode == STATE_HIGH_DEMAND:
            await self.coordinator.async_write_coil(
                self._coil_temporary_lux, "ONE TIME INCREASE"
            )
        else:
            raise ValueError(f"Unsupported operation mode {operation_mode}")
