"""Sensor for Transport for London (TfL)."""

from __future__ import annotations

from datetime import timedelta
import logging
from operator import itemgetter
import typing
from urllib.error import HTTPError, URLError

from tflwrapper import stopPoint

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TfLConfigEntry
from .common import call_tfl_api
from .const import CONF_STOP_POINTS, DOMAIN

ATTR_NEXT_ARRIVALS = "all"
ATTR_NEXT_THREE_ARRIVALS = "next_3"

RAW_ARRIVAL_LINE_NAME = "lineName"
RAW_ARRIVAL_DESTINATION_NAME = "destinationName"
RAW_ARRIVAL_TIME_TO_STATION = "timeToStation"

SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TfLConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TfL sensor(s)."""
    stop_point_api = config_entry.runtime_data

    stop_point_ids: list[str] = config_entry.options[CONF_STOP_POINTS]

    unique_id = config_entry.unique_id

    if typing.TYPE_CHECKING:
        assert unique_id

    devices = []
    for stop_point_id in stop_point_ids:
        try:
            stop_point_info = await call_tfl_api(
                hass, stop_point_api.getByIDs, [stop_point_id], False
            )
            devices.append(
                StopPointSensor(
                    stop_point_api,
                    __get_common_name(stop_point_id, stop_point_info),
                    stop_point_id,
                    unique_id,
                )
            )
        except HTTPError as exception:
            error_code = exception.code
            _LOGGER.exception(
                "Error retrieving stop point info from TfL for stop_point=%s with HTTP error_code=%s, entity will not be created for this stop point",
                stop_point_ids,
                error_code,
            )
        except URLError as exception:
            _LOGGER.exception(
                "Error retrieving stop point info from TfL for stop_point=%s with URLError reason=%s, entity will not be created for this stop point",
                stop_point_ids,
                exception.reason,
            )

    async_add_entities(devices, True)


def __get_common_name(
    stop_point_id: str, stop_point_info: dict[str, typing.Any]
) -> str:
    """Get the common name for the Stop Point.

    In the happy path, the Stop Point Id will match the naptanId, and this is simple.
    For Stop Points where there are many stops that can be grouped together, the TfL API
    will group them and we need to find our target Stop Point Id and get the common name.
    """
    if stop_point_info["naptanId"] == stop_point_id:
        return typing.cast(str, stop_point_info["commonName"])

    # The stop point is more complicated and hierarchical, and we need to find the one that was asked for
    for child_stop_point in stop_point_info["children"]:
        for subchild in child_stop_point["children"]:
            if subchild["naptanId"] == stop_point_id:
                return typing.cast(str, subchild["commonName"])
    return "Unknown"


class StopPointSensor(SensorEntity):
    """Representation of a TfL StopPoint as a Sensor.

    The Sensor does not use a DataUpdateCoordinator because
    TfL doesn't have an API to query multiple stops in a single call. There's a 1:1 mapping between a sensor and an API call.
    """

    _attr_attribution = "Powered by TfL Open Data"
    _attr_icon = "mdi:bus"
    _attr_has_entity_name = True

    def __init__(
        self, stop_point_api: stopPoint, name: str, stop_point_id: str, unique_id: str
    ) -> None:
        """Initialize the TfL StopPoint sensor."""
        self._name = name
        self._attr_name = name
        self._attr_unique_id = f"{unique_id}_{stop_point_id}"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            name="TfL",
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

        self._stop_point_api = stop_point_api
        self._stop_point_id = stop_point_id

    async def async_update(self) -> None:
        """Update Stop Point state."""
        try:
            attributes = {}

            def raw_arrival_to_arrival_mapper(
                raw_arrival: dict[str, typing.Any],
            ) -> dict[str, typing.Any]:
                return {
                    "line_name": raw_arrival[RAW_ARRIVAL_LINE_NAME],
                    "destination_name": raw_arrival[RAW_ARRIVAL_DESTINATION_NAME],
                    "time_to_station": raw_arrival[RAW_ARRIVAL_TIME_TO_STATION],
                }

            raw_arrivals = await call_tfl_api(
                self.hass, self._stop_point_api.getStationArrivals, self._stop_point_id
            )

            if raw_arrivals:
                raw_arrivals_sorted = sorted(
                    raw_arrivals, key=itemgetter(RAW_ARRIVAL_TIME_TO_STATION)
                )

                arrivals = list(map(raw_arrival_to_arrival_mapper, raw_arrivals_sorted))
                _LOGGER.debug("Got arrivals=%s", arrivals)

                arrival_next = arrivals[0]
                arrivals_next_3 = arrivals[:3]

                # Value of the sensor is the seconds to the next arrival and
                # the next 3 and full list are provided as attributes
                self._attr_native_value = arrival_next["time_to_station"]
                self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
                attributes[ATTR_NEXT_THREE_ARRIVALS] = arrivals_next_3
                attributes[ATTR_NEXT_ARRIVALS] = arrivals
            else:
                self._attr_native_value = 0

            self._attr_extra_state_attributes = attributes
            self._attr_available = True

        except HTTPError as exception:
            self._attr_available = False
            error_code = exception.code
            _LOGGER.exception(
                "Error retrieving data from TfL for sensor=%s with HTTP error_code=%s",
                self.name,
                error_code,
            )
        except URLError as exception:
            self._attr_available = False
            _LOGGER.exception(
                "Error retrieving data from TfL for sensor=%s with URLError reason=%s",
                self.name,
                exception.reason,
            )
