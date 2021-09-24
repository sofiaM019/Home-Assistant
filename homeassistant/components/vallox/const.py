"""Constants for the Vallox integration."""

from datetime import timedelta

from vallox_websocket_api import PROFILE as VALLOX_PROFILE

DOMAIN = "vallox"
DEFAULT_NAME = "Vallox"

SIGNAL_VALLOX_STATE_UPDATE = "vallox_state_update"
STATE_PROXY_SCAN_INTERVAL = timedelta(seconds=60)

# Common metric keys and (default) values.
METRIC_KEY_MODE = "A_CYC_MODE"
METRIC_KEY_PROFILE_FAN_SPEED_HOME = "A_CYC_HOME_SPEED_SETTING"
METRIC_KEY_PROFILE_FAN_SPEED_AWAY = "A_CYC_AWAY_SPEED_SETTING"
METRIC_KEY_PROFILE_FAN_SPEED_BOOST = "A_CYC_BOOST_SPEED_SETTING"

MODE_ON = 0
MODE_OFF = 5

DEFAULT_FAN_SPEED_HOME = 50
DEFAULT_FAN_SPEED_AWAY = 25
DEFAULT_FAN_SPEED_BOOST = 65

VALLOX_PROFILE_TO_STR_SETTABLE = {
    VALLOX_PROFILE.HOME: "Home",
    VALLOX_PROFILE.AWAY: "Away",
    VALLOX_PROFILE.BOOST: "Boost",
    VALLOX_PROFILE.FIREPLACE: "Fireplace",
}

VALLOX_PROFILE_TO_STR_REPORTABLE = {
    VALLOX_PROFILE.EXTRA: "Extra",
    **VALLOX_PROFILE_TO_STR_SETTABLE,
}

STR_TO_VALLOX_PROFILE_SETTABLE = {
    value: key for (key, value) in VALLOX_PROFILE_TO_STR_SETTABLE.items()
}

CELL_STATES = {
    0: "heat recovery",
    1: "cool recovery",
    2: "bypass",
    3: "defrost",
}
