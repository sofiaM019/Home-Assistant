"""Support for water heater devices."""
from datetime import timedelta
import functools as ft
import logging
from typing import Any, Dict, List, Optional

import voluptuous as vol

from homeassistant.components.climate.const import ATTR_TARGET_TEMP_STEP
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceDataType
from homeassistant.util.temperature import convert as convert_temperature

# mypy: allow-untyped-defs, no-check-untyped-defs

DEFAULT_MIN_TEMP = 110
DEFAULT_MAX_TEMP = 140

DOMAIN = "water_heater"

ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = timedelta(seconds=60)

SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_SET_TEMPERATURE = "set_temperature"
SERVICE_SET_OPERATION_MODE = "set_operation_mode"

STATE_ECO = "eco"  # TODO rename to OPERATION_MODE_ECO
STATE_ELECTRIC = "electric"
STATE_PERFORMANCE = "performance"
STATE_HIGH_DEMAND = "high_demand"
STATE_HEAT_PUMP = "heat_pump"
STATE_GAS = "gas"

SUPPORT_TARGET_TEMPERATURE = 1
SUPPORT_OPERATION_MODE = 2
SUPPORT_AWAY_MODE = 4

ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_TEMP = "min_temp"
ATTR_AWAY_MODE = "away_mode"
ATTR_OPERATION_MODE = "operation_mode"
ATTR_OPERATION_LIST = "operation_list"
ATTR_TARGET_TEMP_HIGH = "target_temp_high"
ATTR_TARGET_TEMP_LOW = "target_temp_low"
ATTR_CURRENT_TEMPERATURE = "current_temperature"

CONVERTIBLE_ATTRIBUTE = [ATTR_TEMPERATURE]

_LOGGER = logging.getLogger(__name__)

SET_AWAY_MODE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required(ATTR_AWAY_MODE): cv.boolean,
    }
)
SET_TEMPERATURE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(ATTR_TEMPERATURE, "temperature"): vol.Coerce(float),
            vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
            vol.Optional(ATTR_OPERATION_MODE): cv.string,
        }
    )
)
SET_OPERATION_MODE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required(ATTR_OPERATION_MODE): cv.string,
    }
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up water_heater entities."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_AWAY_MODE,
        SET_AWAY_MODE_SCHEMA,
        async_service_away_mode,
        [SUPPORT_AWAY_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_TEMPERATURE,
        SET_TEMPERATURE_SCHEMA,
        async_service_temperature_set,
        [SUPPORT_TARGET_TEMPERATURE],
    )
    component.async_register_entity_service(
        SERVICE_SET_OPERATION_MODE,
        SET_OPERATION_MODE_SCHEMA,
        "async_set_operation_mode",
        [SUPPORT_OPERATION_MODE],
    )
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")
    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> Any:
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> Any:
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class WaterHeaterEntity(Entity):
    """Representation of a water_heater device."""

    @property
    def state(self) -> Optional[str]:
        """Return the current state."""
        return self.current_operation

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return PRECISION_TENTHS
        return PRECISION_WHOLE

    @property
    def capability_attributes(self) -> Optional[Dict[str, Any]]:
        """Return capability attributes."""
        supported_features = self.supported_features or 0

        data = {
            ATTR_MIN_TEMP: show_temp(
                self.hass, self.min_temp, self.temperature_unit, self.precision
            ),
            ATTR_MAX_TEMP: show_temp(
                self.hass, self.max_temp, self.temperature_unit, self.precision
            ),
        }

        if supported_features & SUPPORT_OPERATION_MODE:
            data[ATTR_OPERATION_LIST] = self.operation_list

        if self.target_temperature_step:
            data[ATTR_TARGET_TEMP_STEP] = self.target_temperature_step

        return data

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        data = {
            ATTR_CURRENT_TEMPERATURE: show_temp(
                self.hass,
                self.current_temperature,
                self.temperature_unit,
                self.precision,
            ),
            ATTR_TEMPERATURE: show_temp(
                self.hass,
                self.target_temperature,
                self.temperature_unit,
                self.precision,
            ),
            ATTR_TARGET_TEMP_HIGH: show_temp(
                self.hass,
                self.target_temperature_high,
                self.temperature_unit,
                self.precision,
            ),
            ATTR_TARGET_TEMP_LOW: show_temp(
                self.hass,
                self.target_temperature_low,
                self.temperature_unit,
                self.precision,
            ),
        }

        supported_features = self.supported_features

        if (
            supported_features & SUPPORT_OPERATION_MODE
        ):  # TODO make operation mode (on/off) required
            data[ATTR_OPERATION_MODE] = self.current_operation

        if supported_features & SUPPORT_AWAY_MODE:
            is_away = self.is_away_mode_on
            data[ATTR_AWAY_MODE] = STATE_ON if is_away else STATE_OFF

        return data

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        raise NotImplementedError

    @property
    def current_operation(self) -> Optional[str]:
        """Return current operation ie. eco, electric, performance, ..."""
        return None

    @property
    def operation_list(self) -> Optional[List[str]]:  # TODO Rename to operation_modes
        """Return the list of available operation modes."""
        return None

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return None

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return None

    @property
    def target_temperature_step(self) -> Optional[float]:
        """Return the supported step of target temperature."""
        return None

    @property
    def target_temperature_high(self) -> Optional[float]:
        """Return the highbound target temperature we try to reach."""
        return None

    @property
    def target_temperature_low(self) -> Optional[float]:
        """Return the lowbound target temperature we try to reach."""
        return None

    @property
    def is_away_mode_on(self) -> Optional[bool]:
        """Return true if away mode is on."""
        return None

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        raise NotImplementedError()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        await self.hass.async_add_executor_job(
            ft.partial(self.set_temperature, **kwargs)
        )

    def set_operation_mode(self, operation_mode) -> None:
        """Set new target operation mode."""
        raise NotImplementedError()

    async def async_set_operation_mode(self, operation_mode) -> None:
        """Set new target operation mode."""
        await self.hass.async_add_executor_job(self.set_operation_mode, operation_mode)

    def turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        raise NotImplementedError()

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self.hass.async_add_executor_job(self.turn_away_mode_on)

    def turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        raise NotImplementedError()

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self.hass.async_add_executor_job(self.turn_away_mode_off)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        if hasattr(self, "turn_on"):
            # pylint: disable=no-member
            await self.hass.async_add_executor_job(self.turn_on)
            return

        # Fake turn on
        for mode in (
            STATE_ECO,
            STATE_HEAT_PUMP,
            STATE_GAS,
            STATE_PERFORMANCE,
            STATE_HIGH_DEMAND,
        ):
            if mode not in self.operation_list:
                continue
            await self.async_set_operation_mode(mode)
            break

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        if hasattr(self, "turn_off"):
            # pylint: disable=no-member
            await self.hass.async_add_executor_job(self.turn_off)
            return

        # Fake turn off
        if STATE_OFF in self.operation_list:
            await self.async_set_operation_mode(STATE_OFF)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        raise NotImplementedError()

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return convert_temperature(
            DEFAULT_MIN_TEMP, TEMP_FAHRENHEIT, self.temperature_unit
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return convert_temperature(
            DEFAULT_MAX_TEMP, TEMP_FAHRENHEIT, self.temperature_unit
        )


async def async_service_away_mode(
    entity: WaterHeaterEntity, service: ServiceDataType
) -> None:
    """Handle away mode service."""
    if service.data[ATTR_AWAY_MODE]:
        await entity.async_turn_away_mode_on()
    else:
        await entity.async_turn_away_mode_off()


async def async_service_temperature_set(
    entity: WaterHeaterEntity, service: ServiceDataType
) -> None:
    """Handle set temperature service."""
    hass = entity.hass
    kwargs = {}

    for value, temp in service.data.items():
        if value in CONVERTIBLE_ATTRIBUTE:
            kwargs[value] = convert_temperature(
                temp, hass.config.units.temperature_unit, entity.temperature_unit
            )
        else:
            kwargs[value] = temp

    await entity.async_set_temperature(**kwargs)


class WaterHeaterDevice(WaterHeaterEntity):
    """Representation of a water heater (for backwards compatibility)."""

    def __init_subclass__(cls, **kwargs):
        """Print deprecation warning."""
        super().__init_subclass__(**kwargs)
        _LOGGER.warning(
            "WaterHeaterDevice is deprecated, modify %s to extend WaterHeaterEntity",
            cls.__name__,
        )
