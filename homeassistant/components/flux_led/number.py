"""Support for LED numbers."""
from __future__ import annotations

from typing import cast

from homeassistant import config_entries
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EFFECT_SPEED_SUPPORT_MODES
from .coordinator import FluxLedUpdateCoordinator
from .entity import FluxEntity
from .util import _effect_brightness, _hass_color_modes


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flux lights."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    entities: list[
        FluxSpeedNumber
        | FluxPixelsPerSegmentNumber
        | FluxSegmentsNumber
        | FluxMusicPixelsPerSegmentNumber
        | FluxMusicSegmentsNumber
    ] = []
    name = entry.data[CONF_NAME]
    unique_id = entry.unique_id

    if device.pixels_per_segment:
        entities.append(FluxPixelsPerSegmentNumber(coordinator, unique_id, name))
    if device.segments:
        entities.append(FluxSegmentsNumber(coordinator, unique_id, name))
    if device.music_pixels_per_segment:
        entities.append(FluxMusicPixelsPerSegmentNumber(coordinator, unique_id, name))
    if device.music_segments:
        entities.append(FluxMusicSegmentsNumber(coordinator, unique_id, name))
    if _hass_color_modes(coordinator.device).intersection(EFFECT_SPEED_SUPPORT_MODES):
        entities.append(FluxSpeedNumber(coordinator, unique_id, name))

    if entities:
        async_add_entities(entities)


class FluxConfigNumber(FluxEntity, CoordinatorEntity, NumberEntity):
    """Base class for flux config numbers."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_min_value = 1
    _attr_step = 1
    _attr_mode = NumberMode.SLIDER


class FluxPixelsPerSegmentNumber(FluxConfigNumber):
    """Defines a flux_led pixels per segment number."""

    _attr_max_value = 300
    _attr_icon = "mdi:dots-grid"

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
    ) -> None:
        """Initialize the flux number."""
        super().__init__(coordinator, unique_id, name)
        if unique_id:
            self._attr_unique_id = f"{unique_id}_pixels_per_segment"
        self._attr_name = f"{name} Pixels Per Segment"

    @property
    def value(self) -> int:
        """Return the pixels per segment."""
        assert self._device.pixels_per_segment is not None
        return self._device.pixels_per_segment


class FluxSegmentsNumber(FluxConfigNumber):
    """Defines a flux_led segments number."""

    _attr_max_value = 2048
    _attr_icon = "mdi:segment"

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
    ) -> None:
        """Initialize the flux number."""
        super().__init__(coordinator, unique_id, name)
        if unique_id:
            self._attr_unique_id = f"{unique_id}_segments"
        self._attr_name = f"{name} Segments"

    @property
    def value(self) -> int:
        """Return the segments."""
        assert self._device.segments is not None
        return self._device.segments


class FluxMusicPixelsPerSegmentNumber(FluxConfigNumber):
    """Defines a flux_led music pixels per segment number."""

    _attr_max_value = 150
    _attr_icon = "mdi:dots-grid"

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
    ) -> None:
        """Initialize the flux number."""
        super().__init__(coordinator, unique_id, name)
        if unique_id:
            self._attr_unique_id = f"{unique_id}_music_pixels_per_segment"
        self._attr_name = f"{name} Music Pixels Per Segment"

    @property
    def value(self) -> int:
        """Return the music pixels per segment."""
        assert self._device.music_pixels_per_segment is not None
        return self._device.music_pixels_per_segment


class FluxMusicSegmentsNumber(FluxConfigNumber):
    """Defines a flux_led music segments number."""

    _attr_max_value = 64
    _attr_icon = "mdi:segment"

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
    ) -> None:
        """Initialize the flux number."""
        super().__init__(coordinator, unique_id, name)
        if unique_id:
            self._attr_unique_id = f"{unique_id}_music_segments"
        self._attr_name = f"{name} Music Segments"

    @property
    def value(self) -> int:
        """Return the music segments."""
        assert self._device.music_segments is not None
        return self._device.music_segments


class FluxSpeedNumber(FluxEntity, CoordinatorEntity, NumberEntity):
    """Defines a flux_led speed number."""

    _attr_min_value = 1
    _attr_max_value = 100
    _attr_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:speedometer"

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
    ) -> None:
        """Initialize the flux number."""
        super().__init__(coordinator, unique_id, name)
        self._attr_name = f"{name} Effect Speed"

    @property
    def value(self) -> float:
        """Return the effect speed."""
        return cast(float, self._device.speed)

    async def async_set_value(self, value: float) -> None:
        """Set the flux speed value."""
        current_effect = self._device.effect
        new_speed = int(value)
        if not current_effect:
            raise HomeAssistantError(
                "Speed can only be adjusted when an effect is active"
            )
        if not self._device.speed_adjust_off and not self._device.is_on:
            raise HomeAssistantError("Speed can only be adjusted when the light is on")
        await self._device.async_set_effect(
            current_effect, new_speed, _effect_brightness(self._device.brightness)
        )
        await self.coordinator.async_request_refresh()
