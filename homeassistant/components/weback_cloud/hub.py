"""Weback Cloud communication handler."""
from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

from weback_unofficial.client import WebackApi
from weback_unofficial.vacuum import CleanRobot

from homeassistant.components.weback_cloud.const import (
    CONF_PASSWORD,
    CONF_PHONE_NUMBER,
    CONF_REGION,
    SUPPORTED_DEVICES,
    THING_NAME,
)
from homeassistant.components.weback_cloud.exceptions import InvalidCredentials
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class WebackCloudHub:
    """Weback Cloud Hub."""

    def __init__(
        self, hass: HomeAssistant, data: dict[str, Any] | MappingProxyType[str, Any]
    ) -> None:
        """Initialize Weback Cloud hub."""
        self.hass: HomeAssistant = hass
        self._data: dict[str, Any] | MappingProxyType[str, Any] = data
        self.devices: list[CleanRobot] = []
        self.weback_api: WebackApi = WebackApi

    async def authenticate(self) -> None:
        """Authenticate against Weback Cloud API."""
        region: str = self._data[CONF_REGION]
        phone_number: str = self._data[CONF_PHONE_NUMBER]
        password: str = self._data[CONF_PASSWORD]

        login = f"{region}-{phone_number}"
        self.weback_api = WebackApi(login, password)
        try:
            await self.hass.async_add_executor_job(self.weback_api.get_session)
        except Exception as e:
            raise InvalidCredentials(e)

    async def get_devices(self) -> None:
        """Retrieve supported vacuums from Weback Cloud API."""
        region: str = self._data[CONF_REGION]
        phone_number: str = self._data[CONF_PHONE_NUMBER]
        password: str = self._data[CONF_PASSWORD]

        login = f"{region}-{phone_number}"
        self.weback_api = WebackApi(login, password)
        try:
            for device in await self.hass.async_add_executor_job(
                self.weback_api.device_list
            ):
                description = await self.hass.async_add_executor_job(
                    self.weback_api.get_device_description, device[THING_NAME]
                )
                if description.get("thingTypeName") not in SUPPORTED_DEVICES:
                    _LOGGER.debug(
                        "Device is not supported by this integration: %s",
                        device.__dict__,
                    )
                    continue
                vacuum = CleanRobot(
                    device[THING_NAME], self.weback_api, None, description
                )
                _LOGGER.debug("Adding device: %s", vacuum.__dict__)
                self.devices.append(vacuum)
        except Exception as e:
            _LOGGER.error("Error retrieving devices from Weback Cloud: %s", e)
            raise InvalidCredentials(e)
