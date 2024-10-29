"""Suez water update coordinator."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pysuez import SuezClient
from pysuez.client import PySuezError

from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN


@dataclass
class AggregatedSensorData:
    """Hold suez water aggregated sensor data."""

    value: float
    current_month: Any
    previous_month: Any
    previous_year: Any
    current_year: Any
    history: Any
    highest_monthly_consumption: Any
    attribution: str


class SuezWaterCoordinator(DataUpdateCoordinator[AggregatedSensorData]):
    """Suez water coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SuezClient,
        counter_id: int,
    ) -> None:
        """Initialize suez water coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=12),
            always_update=True,
        )
        self._sync_client = client

    async def _async_update_data(self) -> AggregatedSensorData:
        """Fetch data from API endpoint."""
        async with asyncio.timeout(30):
            return await self.hass.async_add_executor_job(self._fetch_data)

    def _fetch_data(self) -> AggregatedSensorData:
        """Fetch latest data from Suez."""
        try:
            self._sync_client.update()
        except PySuezError as err:
            raise UpdateFailed(
                f"Suez coordinator error communicating with API: {err}"
            ) from err
        current_month = {}
        for item in self._sync_client.attributes["thisMonthConsumption"]:
            current_month[item] = self._sync_client.attributes["thisMonthConsumption"][
                item
            ]
        previous_month = {}
        for item in self._sync_client.attributes["previousMonthConsumption"]:
            previous_month[item] = self._sync_client.attributes[
                "previousMonthConsumption"
            ][item]
        highest_monthly_consumption = self._sync_client.attributes[
            "highestMonthlyConsumption"
        ]
        previous_year = self._sync_client.attributes["lastYearOverAll"]
        current_year = self._sync_client.attributes["thisYearOverAll"]
        history = {}
        for item in self._sync_client.attributes["history"]:
            history[item] = self._sync_client.attributes["history"][item]
        _LOGGER.debug("Retrieved consumption: " + str(self._sync_client.state))
        return AggregatedSensorData(
            self._sync_client.state,
            current_month,
            previous_month,
            previous_year,
            current_year,
            history,
            highest_monthly_consumption,
            self._sync_client.attributes["attribution"],
        )
