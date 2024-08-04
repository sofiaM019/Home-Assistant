"""Constants for the evohome tests."""

from __future__ import annotations

from typing import Final

ACCESS_TOKEN: Final = "at_1dc7z657UKzbhKA..."
REFRESH_TOKEN: Final = "rf_jg68ZCKYdxEI3fF..."
SESSION_ID: Final = "F7181186..."
USERNAME: Final = "test_user@gmail.com"

TEST_INSTALLS: Final = {
    "minimal": {
        "num_zones": 1,
    },  # evohome (single zone, no DHW)
    "default": {
        "num_zones": 7,
        "num_dhw": 1,
    },  # evohome
    "h032585": {
        "num_svcs": 4,
        "num_zones": 1,
    },  # VisionProWifi
    "h099625": {"num_svcs": 4, "num_zones": 2},  # RoundThermostat
    "system_004": {
        "num_svcs": 4,
        "num_zones": 1,
    },  # Multiple
}
