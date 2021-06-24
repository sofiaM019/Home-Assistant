"""Component to interface with various sirens/chimes."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import bind_hass

from .const import (
    ATTR_AVAILABLE_TONES,
    ATTR_DEFAULT_DURATION,
    ATTR_DEFAULT_TONE,
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    DOMAIN,
    SERVICE_SET_DEFAULT_DURATION,
    SERVICE_SET_DEFAULT_TONE,
    SERVICE_SET_VOLUME_LEVEL,
    SUPPORT_DURATION,
    SUPPORT_TONES,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

TURN_ON_SCHEMA = {
    vol.Optional(ATTR_TONE): cv.string,
    vol.Optional(ATTR_DURATION): cv.positive_float,
    vol.Optional(ATTR_VOLUME_LEVEL): cv.small_float,
}


@bind_hass
def is_on(hass: HomeAssistantType, entity_id: str) -> bool:
    """
    Return if the siren is on based on the state machine.

    Async friendly.
    """
    return hass.states.is_state(entity_id, STATE_ON)


def filter_turn_on_params(siren: SirenEntity, params: dict[str, Any]) -> dict[str, Any]:
    """Filter out params not supported by the siren."""
    supported_features = siren.supported_features or 0

    if not supported_features & SUPPORT_TONES:
        params.pop(ATTR_TONE, None)
    if not supported_features & SUPPORT_DURATION:
        params.pop(ATTR_DURATION, None)
    if not supported_features & SUPPORT_VOLUME_SET:
        params.pop(ATTR_VOLUME_LEVEL, None)

    return params


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up siren devices."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    async def async_handle_turn_on_service(
        siren: SirenEntity, call: ServiceCall
    ) -> None:
        """Handle turning a siren on."""
        await siren.async_turn_on(
            **filter_turn_on_params(siren, dict(call.data.get("params", {})))
        )

    component.async_register_entity_service(
        SERVICE_TURN_ON, TURN_ON_SCHEMA, async_handle_turn_on_service, [SUPPORT_TURN_ON]
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, {}, "async_turn_off", [SUPPORT_TURN_OFF]
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE, {}, "async_toggle", [SUPPORT_TURN_ON & SUPPORT_TURN_OFF]
    )
    component.async_register_entity_service(
        SERVICE_SET_DEFAULT_TONE,
        {vol.Required(ATTR_TONE): vol.Any(vol.Coerce(int), cv.string)},
        "async_set_default_tone",
        [SUPPORT_TONES],
    )
    component.async_register_entity_service(
        SERVICE_SET_DEFAULT_DURATION,
        {vol.Required(ATTR_DURATION): cv.positive_float},
        "async_set_default_duration",
        [SUPPORT_DURATION],
    )
    component.async_register_entity_service(
        SERVICE_SET_VOLUME_LEVEL,
        {vol.Required(ATTR_VOLUME_LEVEL): cv.small_float},
        "async_set_volume_level",
        [SUPPORT_VOLUME_SET],
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class SirenEntity(ToggleEntity):
    """Representation of a siren device."""

    _attr_volume_level: float | None = None
    _attr_default_duration: int | None = None
    _attr_default_tone: int | str | None = None
    _attr_available_tones: list[int] | list[str] | None = None

    @property
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return capability attributes."""
        supported_features = self.supported_features or 0

        if supported_features & SUPPORT_TONES:
            return {ATTR_AVAILABLE_TONES: self.available_tones}

        return None

    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        supported_features = self.supported_features or 0
        data: dict[str, Any] = {}

        if self.volume_level is not None:
            data[ATTR_VOLUME_LEVEL] = self.volume_level

        if self.default_duration is not None:
            data[ATTR_DEFAULT_DURATION] = self.default_duration

        if supported_features & SUPPORT_TONES:
            data[ATTR_DEFAULT_TONE] = self.default_tone

        return data

    @property
    def volume_level(self) -> float | None:
        """Return the volume level of the device (0 - 1)."""
        return self._attr_volume_level

    @property
    def default_duration(self) -> int | None:
        """Return the default duration in seconds of the noise."""
        return self._attr_default_duration

    @property
    def default_tone(self) -> int | str | None:
        """
        Return the default tone for the siren.

        Requires SUPPORT_TONES.
        """
        return self._attr_default_tone

    @property
    def available_tones(self) -> list[int] | list[str] | None:
        """
        Return a list of available tones.

        Requires SUPPORT_TONES.
        """
        return self._attr_available_tones

    def set_default_tone(self, tone: int | str) -> None:
        """Set new default tone."""
        raise NotImplementedError()

    async def async_set_default_tone(self, tone: int | str) -> None:
        """Set new default tone."""
        await self.hass.async_add_executor_job(self.set_default_tone, tone)

    def set_volume_level(self, volume_level: float) -> None:
        """Set volume level."""
        raise NotImplementedError()

    async def async_set_volume_level(self, volume_level: float) -> None:
        """Set volume level."""
        await self.hass.async_add_executor_job(self.set_volume_level, volume_level)

    def set_default_duration(self, duration: int) -> None:
        """Set default siren duration in seconds."""
        raise NotImplementedError()

    async def async_set_default_duration(self, duration: int) -> None:
        """Set default siren duration in seconds."""
        await self.hass.async_add_executor_job(self.set_default_duration, duration)
