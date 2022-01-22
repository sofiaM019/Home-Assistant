"""Support for Sensibo wifi-enabled home thermostats."""
from __future__ import annotations

import asyncio
from typing import Any

from aiohttp.client_exceptions import ClientConnectionError
import async_timeout
from pysensibo import SensiboError
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_API_KEY,
    CONF_ID,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ALL, DOMAIN, TIMEOUT, LOGGER
from .coordinator import SensiboDataUpdateCoordinator

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_ID, default=ALL): vol.All(cv.ensure_list, [cv.string]),
    }
)

SENSIBO_TO_HA = {
    "cool": HVAC_MODE_COOL,
    "heat": HVAC_MODE_HEAT,
    "fan": HVAC_MODE_FAN_ONLY,
    "auto": HVAC_MODE_HEAT_COOL,
    "dry": HVAC_MODE_DRY,
    "off": HVAC_MODE_OFF,
}

HA_TO_SENSIBO = {value: key for key, value in SENSIBO_TO_HA.items()}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Sensibo devices."""
    LOGGER.warning(
        "Loading Sensibo via platform setup is deprecated; Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Sensibo climate entry."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SensiboClimate(coordinator, key, hass.config.units.temperature_unit)
        for key in coordinator.data
        # Remove none climate devices
        if coordinator.data[key]["hvac_modes"] and coordinator.data[key]["temp"]
    )


class SensiboClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Sensibo device."""

    coordinator: SensiboDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        key: str,
        temp_unit: str,
    ) -> None:
        """Initiate SensiboClimate."""
        super().__init__(coordinator)
        self._client = coordinator.client
        self._attr_unique_id = coordinator.data[key]["id"]
        self._attr_name = coordinator.data[key]["name"]
        self._attr_temperature_unit = (
            TEMP_CELSIUS
            if coordinator.data[key]["temp_unit"] == "C"
            else TEMP_FAHRENHEIT
        )
        self._attr_supported_features = coordinator.data[key]["features"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data[key]["id"])},
            name=coordinator.data[key]["name"],
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=coordinator.data[key]["model"],
            sw_version=coordinator.data[key]["fw_ver"],
            hw_version=coordinator.data[key]["fw_type"],
            suggested_area=coordinator.data[key]["name"],
        )
        self._temp_unit = temp_unit

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self.coordinator.data[self.unique_id]["humidity"]

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation."""
        return (
            SENSIBO_TO_HA[self.coordinator.data[self.unique_id]["hvac_mode"]]
            if self.coordinator.data[self.unique_id]["on"]
            else HVAC_MODE_OFF
        )

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return [
            SENSIBO_TO_HA[mode]
            for mode in self.coordinator.data[self.unique_id]["hvac_modes"]
        ]

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self.coordinator.data[self.unique_id]["temp"]

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.coordinator.data[self.unique_id]["target_temp"]

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return self.coordinator.data[self.unique_id]["temp_step"]

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self.coordinator.data[self.unique_id]["fan_mode"]

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return self.coordinator.data[self.unique_id]["fan_modes"]

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return self.coordinator.data[self.unique_id]["swing_mode"]

    @property
    def swing_modes(self) -> list[str] | None:
        """Return the list of available swing modes."""
        return self.coordinator.data[self.unique_id]["swing_modes"]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return convert_temperature(
            self.coordinator.data[self.unique_id]["temp_list"][0],
            TEMP_CELSIUS,
            self.temperature_unit,
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return convert_temperature(
            self.coordinator.data[self.unique_id]["temp_list"][-1],
            TEMP_CELSIUS,
            self.temperature_unit,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data[self.unique_id]["available"] and super().available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "calibration_temperature": self.coordinator.data[self.unique_id][
                "calibration_temp"
            ],
            "calibration_humidity": self.coordinator.data[self.unique_id][
                "calibration_hum"
            ],
        }

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := int(kwargs.get(ATTR_TEMPERATURE))) is None:
            return

        if temperature == self.target_temperature:
            return

        if temperature not in self.coordinator.data[self.unique_id]["temp_list"]:
            # Requested temperature is not supported.
            if temperature > self.coordinator.data[self.unique_id]["temp_list"][-1]:
                temperature = self.coordinator.data[self.unique_id]["temp_list"][-1]

            elif temperature < self.coordinator.data[self.unique_id]["temp_list"][0]:
                temperature = self.coordinator.data[self.unique_id]["temp_list"][0]

            else:
                return

        result = await self._async_set_ac_state_property(
            "targetTemperature", temperature
        )
        if result:
            self.coordinator.data[self.unique_id]["temp"] = temperature
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        result = await self._async_set_ac_state_property("fanLevel", fan_mode)
        if result:
            self.coordinator.data[self.unique_id]["fan_mode"] = fan_mode
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            result = await self._async_set_ac_state_property("on", False)
            if result:
                self.coordinator.data[self.unique_id]["on"] = False
                self.async_write_ha_state()
            return

        # Turn on if not currently on.
        if not self.coordinator.data[self.unique_id]["on"]:
            result = await self._async_set_ac_state_property("on", True)
            if result:
                self.coordinator.data[self.unique_id]["on"] = True

        result = await self._async_set_ac_state_property(
            "mode", HA_TO_SENSIBO[hvac_mode]
        )
        if result:
            self.coordinator.data[self.unique_id]["hvac_mode"] = HA_TO_SENSIBO[
                hvac_mode
            ]
            self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        result = await self._async_set_ac_state_property("swing", swing_mode)
        if result:
            self.coordinator.data[self.unique_id]["swing_mode"] = swing_mode
            self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn Sensibo unit on."""
        result = await self._async_set_ac_state_property("on", True)
        if result:
            self.coordinator.data[self.unique_id]["on"] = True
            self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn Sensibo unit on."""
        result = await self._async_set_ac_state_property("on", False)
        if result:
            self.coordinator.data[self.unique_id]["on"] = False
            self.async_write_ha_state()

    async def _async_set_ac_state_property(
        self, name: str, value: str, assumed_state: bool = False
    ) -> bool:
        """Set AC state."""
        result = {}
        try:
            async with async_timeout.timeout(TIMEOUT):
                result = await self._client.async_set_ac_state_property(
                    self.unique_id,
                    name,
                    value,
                    self.coordinator.data[self.unique_id]["ac_states"],
                    assumed_state,
                )
        except (
            ClientConnectionError,
            asyncio.TimeoutError,
            SensiboError,
        ) as err:
            raise HomeAssistantError(
                f"Failed to set AC state for device {self.name} to Sensibo servers: {err}"
            ) from err
        if result["status"] == "Success":
            return True
        return False
