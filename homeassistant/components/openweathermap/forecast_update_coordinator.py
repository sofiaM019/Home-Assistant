"""Forecast data coordinator for the OpenWeatherMap (OWM) service."""
from datetime import timedelta
import logging

import async_timeout
from pyowm.exceptions.api_call_error import APICallError
from pyowm.exceptions.api_response_error import UnauthorizedError

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_API_FORECAST, CONDITION_CLASSES, DOMAIN

_LOGGER = logging.getLogger(__name__)

FORECAST_UPDATE_INTERVAL = timedelta(minutes=30)


class ForecastUpdateCoordinator(DataUpdateCoordinator):
    """Forecast data update coordinator."""

    def __init__(self, owm, latitude, longitude, forecast_mode, hass):
        """Initialize coordinator."""
        self._forecast_mode = forecast_mode
        self._owm_client = owm
        self._latitude = latitude
        self._longitude = longitude
        self._forecast_limit = 15

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=FORECAST_UPDATE_INTERVAL
        )

    async def _async_update_data(self):
        data = {}
        with async_timeout.timeout(20):
            try:
                forecast_response = await self._update_forecast()
                data[ATTR_API_FORECAST] = self._convert_forecast(forecast_response)
            except (APICallError, UnauthorizedError) as error:
                raise UpdateFailed(error)

        return data

    async def _update_forecast(self):
        if self._forecast_mode == "daily":
            forecast_at = self._owm_client.daily_forecast_at_coords(
                self._latitude, self._longitude, self._forecast_limit
            )
        else:
            forecast_at = self._owm_client.three_hours_forecast_at_coords(
                self._latitude, self._longitude
            )
        forecast_values = forecast_at.get_forecast()

        if self._forecast_mode == "freedaily":
            return forecast_values.get_weathers()[::8]
        return forecast_values.get_weathers()

    def _convert_forecast(self, forecast_response):
        if self._forecast_mode == "daily":
            return map(_convert_daily_forecast, forecast_response)
        return map(_convert_other_forecast, forecast_response)


def _convert_daily_forecast(entry):
    return {
        ATTR_FORECAST_TIME: entry.get_reference_time("unix") * 1000,
        ATTR_FORECAST_TEMP: entry.get_temperature("celsius").get("day"),
        ATTR_FORECAST_TEMP_LOW: entry.get_temperature("celsius").get("night"),
        ATTR_FORECAST_PRECIPITATION: _calc_daily_precipitation(
            entry.get_rain().get("all"), entry.get_snow().get("all")
        ),
        ATTR_FORECAST_WIND_SPEED: entry.get_wind().get("speed"),
        ATTR_FORECAST_WIND_BEARING: entry.get_wind().get("deg"),
        ATTR_FORECAST_CONDITION: _get_condition(entry),
    }


def _convert_other_forecast(entry):
    return {
        ATTR_FORECAST_TIME: entry.get_reference_time("unix") * 1000,
        ATTR_FORECAST_TEMP: entry.get_temperature("celsius").get("temp"),
        ATTR_FORECAST_PRECIPITATION: _calc_precipitation(entry),
        ATTR_FORECAST_CONDITION: _get_condition(entry),
    }


def _calc_daily_precipitation(rain, snow):
    """Calculate the precipitation."""
    rain_value = 0 if rain is None else rain
    snow_value = 0 if snow is None else snow
    if round(rain_value + snow_value, 1) == 0:
        return None
    return round(rain_value + snow_value, 1)


def _calc_precipitation(entry):
    return (
        round(entry.get_rain().get("3h"), 1)
        if entry.get_rain().get("3h") is not None
        and (round(entry.get_rain().get("3h"), 1) > 0)
        else None
    )


def _get_condition(entry):
    return [k for k, v in CONDITION_CLASSES.items() if entry.get_weather_code() in v][0]
