"""Initialization of ATAG One climate platform."""
from typing import List, Optional

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    PRESET_AWAY,
    PRESET_BOOST,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE

from . import CLIMATE, DOMAIN, AtagEntity

PRESET_MAP = {
    "Manual": "manual",
    "Auto": "automatic",
    "Extend": "extend",
    PRESET_AWAY: "vacation",
    PRESET_BOOST: "fireplace",
}
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
HVAC_MODES = [HVAC_MODE_AUTO, HVAC_MODE_HEAT]


async def async_setup_entry(hass, entry, async_add_entities):
    """Load a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AtagThermostat(coordinator, CLIMATE)])


class AtagThermostat(AtagEntity, ClimateEntity):
    """Atag climate device."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def hvac_mode(self) -> Optional[str]:
        """Return hvac operation ie. heat, cool mode."""
        if self.coordinator.data.climate.hvac_mode in HVAC_MODES:
            return self.coordinator.data.climate.hvac_mode
        return None

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return HVAC_MODES

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation."""
        on = self.coordinator.data.climate.status
        return CURRENT_HVAC_HEAT if on else CURRENT_HVAC_IDLE

    @property
    def temperature_unit(self) -> Optional[str]:
        """Return the unit of measurement."""
        return self.coordinator.data.climate.temp_unit

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self.coordinator.data.climate.temperature

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self.coordinator.data.climate.target_temperature

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., auto, manual, fireplace, extend, etc."""
        return list(PRESET_MAP.keys())[
            list(PRESET_MAP.values()).index(self.coordinator.data.climate.preset_mode)
        ]

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return list(PRESET_MAP.keys())

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        await self.coordinator.data.climate.set_temp(kwargs.get(ATTR_TEMPERATURE))
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        await self.coordinator.data.climate.set_hvac_mode(hvac_mode)
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.coordinator.data.climate.set_preset_mode(PRESET_MAP[preset_mode])
        self.async_write_ha_state()
