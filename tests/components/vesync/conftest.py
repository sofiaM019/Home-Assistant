"""Configuration for VeSync tests."""
from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest
from pyvesync import VeSync
from pyvesync.helpers import Helpers
from pyvesync.vesyncbulb import VeSyncBulb
from pyvesync.vesyncfan import VeSyncAirBypass
from pyvesync.vesyncoutlet import VeSyncOutlet
from pyvesync.vesyncswitch import VeSyncSwitch

from homeassistant.components.vesync import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant, config) -> ConfigEntry:
    """Create a mock VeSync config entry."""
    entry = MockConfigEntry(
        title="VeSync",
        domain=DOMAIN,
        data=config[DOMAIN],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture() -> ConfigType:
    """Create hass config fixture."""
    return {DOMAIN: {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}}


@pytest.fixture(name="manager")
def manager_fixture() -> VeSync:
    """Create a mock VeSync manager fixture."""

    outlets = []
    switches = []
    fans = []
    bulbs = []

    mock_vesync = Mock(VeSync)
    mock_vesync.login = Mock(return_value=True)
    mock_vesync.update = Mock()
    mock_vesync.outlets = outlets
    mock_vesync.switches = switches
    mock_vesync.fans = fans
    mock_vesync.bulbs = bulbs
    mock_vesync._dev_list = {
        "fans": fans,
        "outlets": outlets,
        "switches": switches,
        "bulbs": bulbs,
    }
    mock_vesync.account_id = "account_id"
    mock_vesync.time_zone = "America/New_York"
    mock = Mock(return_value=mock_vesync)

    with patch("homeassistant.components.vesync.VeSync", new=mock):
        # , patch(
        #     "pyvesync.vesync.VeSync", new=mock
        # ):
        yield mock_vesync


# @pytest.fixture(name="manager2")
# def manager2_fixture() -> VeSync:
#     """Create a mock VeSync manager fixture."""
#     vesync = VeSync("user", "pass", "America/New_York")
#     # patch.object(vesync, "get_devices", return_value=True)
#     # patch.object(vesync, "login", return_value=True)
#     # patch.object(vesync, "update", return_value=True)
#     #    mock = Mock(return_value=vesync)

#     return patch("homeassistant.components.vesync.VeSync", new=vesync):
#         yield vesync


@pytest.fixture(name="helper")
def helper_fixture() -> Helpers:
    """Create a mock VeSync Helpers fixture."""
    helper = MagicMock(Helpers)
    helper.call_api = Mock(return_vale="Chuck")
    return helper


@pytest.fixture(name="fan")
def fan_fixture():
    """Create a mock VeSync fan fixture."""
    mock_fixture = Mock(VeSyncAirBypass)
    return mock_fixture


@pytest.fixture(name="bulb")
def bulb_fixture():
    """Create a mock VeSync bulb fixture."""
    mock_fixture = Mock(VeSyncBulb)
    return mock_fixture


@pytest.fixture(name="switch")
def switch_fixture():
    """Create a mock VeSync switch fixture."""
    mock_fixture = Mock(VeSyncSwitch)
    mock_fixture.is_dimmable = Mock(return_value=False)
    return mock_fixture


@pytest.fixture(name="dimmable_switch")
def dimmable_switch_fixture():
    """Create a mock VeSync switch fixture."""
    mock_fixture = Mock(VeSyncSwitch)
    mock_fixture.is_dimmable = Mock(return_value=True)
    return mock_fixture


@pytest.fixture(name="outlet")
def outlet_fixture():
    """Create a mock VeSync outlet fixture."""
    mock_fixture = Mock(VeSyncOutlet)
    return mock_fixture
