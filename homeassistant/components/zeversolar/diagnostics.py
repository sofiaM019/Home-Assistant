"""Provides diagnostics for local calendar."""

from typing import Any

from zeversolar import ZeverSolarData

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import ZeversolarCoordinator

TO_REDACT = {"serial_or_registry_id", "registry_key", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator: ZeversolarCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    data: ZeverSolarData = coordinator.data

    payload: dict[str, Any] = {
        "wifi_enabled": data.wifi_enabled,
        "serial_or_registry_id": data.serial_or_registry_id,
        "registry_key": data.registry_key,
        "hardware_version": data.hardware_version,
        "software_version": data.software_version,
        "reported_datetime": data.reported_datetime,
        "communication_status": data.communication_status.value,
        "num_inverters": data.num_inverters,
        "serial_number": data.serial_number,
        "pac": data.pac,
        "status": data.status.value,
        "meter_status": data.meter_status.value,
    }

    return async_redact_data(payload, TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    coordinator: ZeversolarCoordinator = hass.data[DOMAIN][entry.entry_id]

    updateInterval = (
        None
        if coordinator.update_interval is None
        else coordinator.update_interval.total_seconds()
    )

    return {
        "name": coordinator.name,
        "always_update": coordinator.always_update,
        "last_update_success": coordinator.last_update_success,
        "update_interval": updateInterval,
    }
