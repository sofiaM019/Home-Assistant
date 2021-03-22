"""The motionEye integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from motioneye_client.client import (
    MotionEyeClient,
    MotionEyeClientError,
    MotionEyeClientInvalidAuth,
)
from motioneye_client.const import KEY_CAMERAS, KEY_ID, KEY_NAME

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SOURCE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USERNAME,
    CONF_CLIENT,
    CONF_COORDINATOR,
    CONF_ON_UNLOAD,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SIGNAL_CAMERA_ADD,
    SIGNAL_CAMERA_REMOVE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]


def create_motioneye_client(
    *args: Any,
    **kwargs: Any,
) -> MotionEyeClient:
    """Create a MotionEyeClient."""
    return MotionEyeClient(*args, **kwargs)


def get_motioneye_config_unique_id(host: str, port: int) -> str:
    """Get the unique_id for a motionEye config."""
    return f"{host}:{port}"


def get_motioneye_device_unique_id(host: str, port: int, camera_id: int) -> str:
    """Get the unique_id for a motionEye device."""
    return f"{get_motioneye_config_unique_id(host, port)}_{camera_id}"


def get_motioneye_entity_unique_id(
    host: str, port: int, camera_id: int, entity_type: str
) -> str:
    """Get the unique_id for a motionEye entity."""
    return f"{get_motioneye_device_unique_id(host, port, camera_id)}_{entity_type}"


def get_camera_from_cameras(
    camera_id: int, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Get an individual camera dict from a multiple cameras data response."""
    for camera in data.get(KEY_CAMERAS) or []:
        if camera.get(KEY_ID) == camera_id:
            return camera
    return None


def is_acceptable_camera(camera: dict[str, Any]) -> bool:
    """Determine if a camera dict is acceptable."""
    return camera and KEY_ID in camera and KEY_NAME in camera


@callback
def listen_for_camera_updates(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_func: Callable,
    remove_func: Callable,
) -> None:
    """Listen for camera additions/removals."""

    hass.data[DOMAIN][entry.entry_id][CONF_ON_UNLOAD].extend(
        [
            async_dispatcher_connect(
                hass,
                SIGNAL_CAMERA_ADD.format(entry.entry_id),
                add_func,
            ),
            async_dispatcher_connect(
                hass,
                SIGNAL_CAMERA_REMOVE.format(entry.entry_id),
                remove_func,
            ),
        ]
    )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]):
    """Set up the motionEye component."""
    hass.data[DOMAIN] = {}
    return True


async def _create_reauth_flow(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_REAUTH}, data=config_entry.data
        )
    )


def remove_motioneye_entity(
    registry: EntityRegistry, platform: str, unique_id: str
) -> None:
    """Remove a given entity."""
    entity_id = registry.async_get_entity_id(platform, DOMAIN, unique_id)

    if entity_id:
        registry.async_remove(entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up motionEye from a config entry."""
    client = create_motioneye_client(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        admin_username=entry.data.get(CONF_ADMIN_USERNAME),
        admin_password=entry.data.get(CONF_ADMIN_PASSWORD),
        surveillance_username=entry.data.get(CONF_SURVEILLANCE_USERNAME),
        surveillance_password=entry.data.get(CONF_SURVEILLANCE_PASSWORD),
    )

    try:
        await client.async_client_login()
    except MotionEyeClientInvalidAuth:
        await client.async_client_close()
        await _create_reauth_flow(hass, entry)
        return False
    except MotionEyeClientError:
        await client.async_client_close()
        raise ConfigEntryNotReady

    async def async_update_data():
        try:
            return await client.async_get_cameras()
        except MotionEyeClientError as exc:
            raise UpdateFailed(f"Error communicating with API: {exc}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_CLIENT: client,
        CONF_COORDINATOR: coordinator,
        CONF_ON_UNLOAD: [],
    }

    current_camera_ids: set[int] = set()

    def _async_process_motioneye_cameras() -> None:
        """Process motionEye camera additions and removals."""
        inbound_camera_ids: set[int] = set()
        if KEY_CAMERAS not in coordinator.data:
            return

        for camera in coordinator.data[KEY_CAMERAS]:
            if not is_acceptable_camera(camera):
                return
            camera_id = camera[KEY_ID]
            inbound_camera_ids.add(camera_id)
            if camera_id in current_camera_ids:
                continue
            current_camera_ids.add(camera_id)

            async_dispatcher_send(
                hass,
                SIGNAL_CAMERA_ADD.format(entry.entry_id),
                camera,
            )

        # Remove cameras that are are not present on the motionEye server.
        cameras_to_remove = current_camera_ids - inbound_camera_ids
        for camera_id in cameras_to_remove:
            current_camera_ids.remove(camera_id)
            async_dispatcher_send(
                hass, SIGNAL_CAMERA_REMOVE.format(entry.entry_id), camera_id
            )

    async def setup_then_listen() -> None:
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, platform)
                for platform in PLATFORMS
            ]
        )
        hass.data[DOMAIN][entry.entry_id][CONF_ON_UNLOAD].append(
            coordinator.async_add_listener(_async_process_motioneye_cameras)
        )
        await coordinator.async_refresh()

    hass.async_create_task(setup_then_listen())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        config_data = hass.data[DOMAIN].pop(entry.entry_id)
        await config_data[CONF_CLIENT].async_client_close()
        for func in config_data[CONF_ON_UNLOAD]:
            func()

    return unload_ok
