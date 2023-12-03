"""Coordinator for Streamlabs water integration."""
from dataclasses import dataclass
from datetime import timedelta
import logging

from streamlabswater.streamlabswater import StreamlabsClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass(slots=True)
class StreamlabsData:
    """Class to hold Streamlabs data."""

    is_away: bool
    name: str
    daily_usage: float
    monthly_usage: float
    yearly_usage: float


class StreamlabsCoordinator(DataUpdateCoordinator[dict[str, StreamlabsData]]):
    """Coordinator for Streamlabs."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: StreamlabsClient,
    ) -> None:
        """Coordinator for Streamlabs."""
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name="Streamlabs",
            update_interval=timedelta(seconds=60),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, StreamlabsData]:
        return await self.hass.async_add_executor_job(self._update_data)

    def _update_data(self) -> dict[str, StreamlabsData]:
        locations = self.client.get_locations()
        res = {}
        for location in locations:
            location_id = location["locationId"]
            water_usage = self.client.get_water_usage_summary(location_id)
            location = self.client.get_location(location_id)
            res[location_id] = StreamlabsData(
                is_away=location["homeAway"] == "away",
                name=location["name"],
                daily_usage=round(water_usage["today"], 1),
                monthly_usage=round(water_usage["thisMonth"], 1),
                yearly_usage=round(water_usage["thisYear"], 1),
            )
        return res
