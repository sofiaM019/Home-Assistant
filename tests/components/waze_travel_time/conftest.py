"""Fixtures for Waze Travel Time tests."""

from unittest.mock import patch

import pytest
from pywaze.route_calculator import CalcRoutesResponse, WRCError


@pytest.fixture(name="mock_update")
def mock_update_fixture():
    """Mock an update to the sensor."""
    with patch(
        "pywaze.route_calculator.WazeRouteCalculator.calc_routes",
        return_value=[
            CalcRoutesResponse(
                distance=300,
                duration=150,
                name="E1337 - Teststreet",
                street_names=["E1337", "IncludeThis", "Teststreet"],
            ),
            CalcRoutesResponse(
                distance=500,
                duration=600,
                name="E0815 - Otherstreet",
                street_names=["E0815", "ExcludeThis", "Otherstreet"],
            ),
        ],
    ) as mock_wrc:
        yield mock_wrc


@pytest.fixture(name="validate_config_entry")
def validate_config_entry_fixture(mock_update):
    """Return valid config entry."""
    mock_update.return_value = None
    return mock_update


@pytest.fixture(name="invalidate_config_entry")
def invalidate_config_entry_fixture(validate_config_entry):
    """Return invalid config entry."""
    validate_config_entry.side_effect = WRCError("test")
    return validate_config_entry


@pytest.fixture(name="bypass_platform_setup")
def bypass_platform_setup_fixture():
    """Bypass platform setup."""
    with patch(
        "homeassistant.components.waze_travel_time.sensor.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(name="bypass_setup")
def bypass_setup_fixture():
    """Bypass entry setup."""
    with patch(
        "homeassistant.components.waze_travel_time.async_setup_entry",
        return_value=True,
    ):
        yield
