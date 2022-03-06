"""Base entity for Sensibo integration."""
from __future__ import annotations

from typing import Any

import async_timeout

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, SENSIBO_ERRORS, TIMEOUT
from .coordinator import MotionSensor, SensiboDataUpdateCoordinator
from .sensor import SensiboSensorEntityDescription


class SensiboBaseEntity(CoordinatorEntity):
    """Representation of a Sensibo numbers."""

    coordinator: SensiboDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initiate Sensibo Number."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._client = coordinator.client
        device = coordinator.data.parsed[device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["id"])},
            name=device["name"],
            connections={(CONNECTION_NETWORK_MAC, device["mac"])},
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=device["model"],
            sw_version=device["fw_ver"],
            hw_version=device["fw_type"],
            suggested_area=device["name"],
        )

    @property
    def device_data(self) -> dict[str, Any]:
        """Return data for device."""
        return self.coordinator.data.parsed[self._device_id]

    async def async_send_command(
        self, command: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Send command to Sensibo api."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                result = await self.async_send_api_call(command, params)
        except SENSIBO_ERRORS as err:
            raise HomeAssistantError(
                f"Failed to send command {command} for device {self.name} to Sensibo servers: {err}"
            ) from err

        LOGGER.debug("Result: %s", result)
        return result

    async def async_send_api_call(
        self, command: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Send api call."""
        result: dict[str, Any] = {"status": None}
        if command == "set_calibration":
            result = await self._client.async_set_calibration(
                self._device_id,
                params["data"],
            )
        if command == "set_ac_state":
            result = await self._client.async_set_ac_state_property(
                self._device_id,
                params["name"],
                params["value"],
                params["ac_states"],
                params["assumed_state"],
            )
        return result


class SensiboMotionBaseEntity(CoordinatorEntity):
    """Representation of a Sensibo numbers."""

    coordinator: SensiboDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        sensor_id: str,
        sensor_data: MotionSensor,
        entity_description: SensiboSensorEntityDescription,
    ) -> None:
        """Initiate Sensibo Number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{sensor_id}-{entity_description.key}"
        self._attr_name = f"{sensor_data.model} {entity_description.name}"
        self._device_id = device_id
        self._sensor_id = sensor_id
        self._client = coordinator.client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor_id)},
            name=f"{sensor_data.model} {entity_description.name}",
            via_device=(DOMAIN, device_id),
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=sensor_data.model,
            sw_version=sensor_data.fw_ver,
            hw_version=sensor_data.fw_type,
        )
