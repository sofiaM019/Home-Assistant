"""Media player support for Android TV Remote."""
from __future__ import annotations

import asyncio
from typing import Any

from androidtvremote2 import AndroidTVRemote

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AndroidTVRemoteBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Android TV media player entity based on a config entry."""
    api: AndroidTVRemote = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([AndroidTVRemoteMediaPlayerEntity(api, config_entry)])


class AndroidTVRemoteMediaPlayerEntity(AndroidTVRemoteBaseEntity, MediaPlayerEntity):
    """Android TV Remote Media Player Entity."""

    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )

    def __init__(self, api: AndroidTVRemote, config_entry: ConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(api, config_entry)

        self._volume_max: int | None = None
        self._volume_set_task: asyncio.Task | None = None
        self._channel_set_task: asyncio.Task | None = None

        self._update_current_app(api.current_app)
        self._update_volume_info(api.volume_info)

        @callback
        def current_app_updated(current_app: str) -> None:
            self._update_current_app(current_app)
            self.async_write_ha_state()

        @callback
        def volume_info_updated(volume_info: dict[str, str | bool]) -> None:
            self._update_volume_info(volume_info)
            if not self._volume_set_task or self._volume_set_task.done():
                self.async_write_ha_state()

        api.add_current_app_updated_callback(current_app_updated)
        api.add_volume_info_updated_callback(volume_info_updated)

    def _update_current_app(self, current_app: str) -> None:
        """Update current app info."""
        self._attr_app_id = current_app
        self._attr_app_name = current_app

    def _update_volume_info(self, volume_info: dict[str, str | bool]) -> None:
        """Update volume info."""
        if volume_info["max"]:
            self._volume_max = int(volume_info["max"])
            self._attr_volume_level = int(volume_info["level"]) / self._volume_max
            self._attr_is_volume_muted = bool(volume_info["muted"])
            self._attr_supported_features |= MediaPlayerEntityFeature.VOLUME_SET
        else:
            self._volume_max = None
            self._attr_volume_level = None
            self._attr_is_volume_muted = None
            self._attr_supported_features &= ~MediaPlayerEntityFeature.VOLUME_SET

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        if self._attr_is_on:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    async def async_turn_on(self) -> None:
        """Turn the Android TV on."""
        if not self._attr_is_on:
            self._send_key_command("POWER")

    async def async_turn_off(self) -> None:
        """Turn the Android TV off."""
        if self._attr_is_on:
            self._send_key_command("POWER")

    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        self._send_key_command("VOLUME_UP")

    async def async_volume_down(self) -> None:
        """Turn volume up for media player."""
        self._send_key_command("VOLUME_DOWN")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if mute != self.is_volume_muted:
            self._send_key_command("VOLUME_MUTE")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        assert self._volume_max
        assert self._attr_volume_level is not None
        if self._volume_set_task:
            self._volume_set_task.cancel()
        diff = volume - self._attr_volume_level
        count = abs(round(diff * self._volume_max))
        key_code = "VOLUME_UP" if diff > 0 else "VOLUME_DOWN"
        self._volume_set_task = asyncio.create_task(
            self._send_key_commands([key_code] * count)
        )
        await self._volume_set_task

    async def async_media_play(self) -> None:
        """Send play command."""
        self._send_key_command("MEDIA_PLAY")

    async def async_media_pause(self) -> None:
        """Send pause command."""
        self._send_key_command("MEDIA_PAUSE")

    async def async_media_play_pause(self) -> None:
        """Send play/pause command."""
        self._send_key_command("MEDIA_PLAY_PAUSE")

    async def async_media_stop(self) -> None:
        """Send stop command."""
        self._send_key_command("MEDIA_STOP")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        self._send_key_command("MEDIA_PREVIOUS")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        self._send_key_command("MEDIA_NEXT")

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if media_type == MediaType.CHANNEL:
            if not media_id.isnumeric():
                raise ValueError(f"Channel must be numeric: {media_id}")
            if self._channel_set_task:
                self._channel_set_task.cancel()
            self._channel_set_task = asyncio.create_task(
                self._send_key_commands(list(media_id))
            )
            await self._channel_set_task
            return

        if media_type == MediaType.URL:
            self._send_launch_app_command(media_id)
            return

        raise ValueError(f"Invalid media type: {media_type}")
