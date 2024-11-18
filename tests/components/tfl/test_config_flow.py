"""Test the Transport for London config flow."""

from unittest.mock import Mock, patch
from urllib.error import HTTPError

import pytest

from homeassistant import config_entries
from homeassistant.components.tfl.common import CannotConnect, InvalidAuth
from homeassistant.components.tfl.config_flow import STEP_STOP_POINTS_DATA_SCHEMA
from homeassistant.components.tfl.const import (
    CONF_API_APP_KEY,
    CONF_STOP_POINTS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_flow_user_init(hass: HomeAssistant) -> None:
    """Test the initialization of the form in the first step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["handler"] == "tfl"
    assert result["errors"] == {}


async def test_flow_stops_form_is_shown(hass: HomeAssistant) -> None:
    """Test the initialization of the form in the second step of the config flow."""
    user_config_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert user_config_flow_result["type"] == FlowResultType.FORM
    assert user_config_flow_result["errors"] == {}

    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getCategories",
        return_value={},
    ):
        stops_config_flow_init_result = await hass.config_entries.flow.async_configure(
            user_config_flow_result["flow_id"],
            user_input={CONF_API_APP_KEY: "appy_appy_app_key"},
        )
        await hass.async_block_till_done()

    # Validate that the stops form is shown
    assert stops_config_flow_init_result["type"] == FlowResultType.FORM
    assert stops_config_flow_init_result["step_id"] == "stop_point"
    assert stops_config_flow_init_result["handler"] == "tfl"
    assert stops_config_flow_init_result["errors"] == {}
    assert stops_config_flow_init_result["data_schema"] == STEP_STOP_POINTS_DATA_SCHEMA


@patch("homeassistant.components.tfl.config_flow.stopPoint")
async def test_flow_stops_does_multiple_stops(m_stopPoint, hass: HomeAssistant) -> None:
    """Test that the stops step allows for multiple stops to be entered."""

    m_stop_point_api = Mock()
    m_stop_point_api.getStationArrivals = Mock()
    m_stopPoint.return_value = m_stop_point_api

    user_config_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert user_config_flow_result["type"] == FlowResultType.FORM
    assert user_config_flow_result["errors"] == {}

    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getCategories",
        return_value={},
    ):
        stops_config_flow_init_result = await hass.config_entries.flow.async_configure(
            user_config_flow_result["flow_id"],
            user_input={CONF_API_APP_KEY: "appy_appy_app_key"},
        )
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getStationArrivals",
        return_value={},
    ):
        stops_config_success_result = await hass.config_entries.flow.async_configure(
            stops_config_flow_init_result["flow_id"],
            user_input={CONF_STOP_POINTS: ["AAAAAAAA1", "AAAAAAAA2"]},
        )
        await hass.async_block_till_done()

    # assert expected == stops_config_success_result
    assert stops_config_success_result["type"] == FlowResultType.CREATE_ENTRY
    assert stops_config_success_result["handler"] == "tfl"
    assert stops_config_success_result["title"] == "Transport for London"
    assert stops_config_success_result["data"] == {
        CONF_API_APP_KEY: "appy_appy_app_key"
    }
    assert stops_config_success_result["options"] == {
        CONF_STOP_POINTS: ["AAAAAAAA1", "AAAAAAAA2"]
    }
    assert stops_config_success_result["version"] == 1


@patch("homeassistant.components.tfl.config_flow.stopPoint")
async def test_flow_stops_creates_config_entry(
    m_stopPoint, hass: HomeAssistant
) -> None:
    """Test the Config Entry is successfully created."""
    m_stop_point_api = Mock()
    m_stop_point_api.getStationArrivals = Mock()
    m_stopPoint.return_value = m_stop_point_api

    user_config_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert user_config_flow_result["type"] == FlowResultType.FORM
    assert user_config_flow_result["errors"] == {}

    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getCategories",
        return_value={},
    ):
        stops_config_flow_init_result = await hass.config_entries.flow.async_configure(
            user_config_flow_result["flow_id"],
            user_input={CONF_API_APP_KEY: "appy_appy_app_key"},
        )
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getStationArrivals",
        return_value={},
    ):
        stops_config_success_result = await hass.config_entries.flow.async_configure(
            stops_config_flow_init_result["flow_id"],
            user_input={CONF_STOP_POINTS: ["AAAAAAAA1"]},
        )
        await hass.async_block_till_done()

    # Validate that config entry was created
    assert stops_config_success_result["type"] == FlowResultType.CREATE_ENTRY
    assert stops_config_success_result["handler"] == "tfl"
    assert stops_config_success_result["title"] == "Transport for London"
    assert stops_config_success_result["data"] == {
        CONF_API_APP_KEY: "appy_appy_app_key"
    }
    assert stops_config_success_result["options"] == {CONF_STOP_POINTS: ["AAAAAAAA1"]}
    assert stops_config_success_result["version"] == 1


@patch("homeassistant.components.tfl.config_flow.stopPoint")
async def test_form_no_stop(m_stopPoint, hass: HomeAssistant) -> None:
    """Test we handle no stops being entered."""
    m_stop_point_api = Mock()
    m_stop_point_api.getStationArrivals = Mock()
    m_stopPoint.return_value = m_stop_point_api

    user_config_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert user_config_flow_result["type"] == FlowResultType.FORM
    assert user_config_flow_result["errors"] == {}

    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getStationArrivals",
        return_value={},
    ):
        stops_config_flow_init_result = await hass.config_entries.flow.async_configure(
            user_config_flow_result["flow_id"],
            user_input={CONF_API_APP_KEY: "appy_appy_app_key"},
        )
        await hass.async_block_till_done()

    with patch("homeassistant.components.tfl.async_setup_entry", return_value=True):
        stops_config_error_result = await hass.config_entries.flow.async_configure(
            stops_config_flow_init_result["flow_id"],
        )

    assert stops_config_error_result["type"] == FlowResultType.FORM
    assert stops_config_error_result["step_id"] == "stop_point"
    assert stops_config_error_result["handler"] == "tfl"
    assert stops_config_error_result["errors"] == {}
    assert stops_config_error_result["data_schema"] == STEP_STOP_POINTS_DATA_SCHEMA


@patch("homeassistant.components.tfl.config_flow.stopPoint")
async def test_invalid_stop_id(m_stopPoint, hass: HomeAssistant) -> None:
    """Test we handle an invalid stop id being entered."""
    m_stop_point_api = Mock()
    m_stop_point_api.getStationArrivals = Mock(
        side_effect=HTTPError("http://test", 404, "Not Found", None, None)
    )
    m_stopPoint.return_value = m_stop_point_api

    user_config_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert user_config_flow_result["type"] == FlowResultType.FORM
    assert user_config_flow_result["errors"] == {}

    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getStationArrivals",
        return_value={},
    ):
        stops_config_flow_init_result = await hass.config_entries.flow.async_configure(
            user_config_flow_result["flow_id"],
            user_input={CONF_API_APP_KEY: "appy_appy_app_key"},
        )
        await hass.async_block_till_done()

    with patch("homeassistant.components.tfl.async_setup_entry", return_value=True):
        stops_config_error_result = await hass.config_entries.flow.async_configure(
            stops_config_flow_init_result["flow_id"],
            user_input={CONF_STOP_POINTS: ["DOES_NOT_EXIST"]},
        )

    assert stops_config_error_result["type"] == FlowResultType.FORM
    assert stops_config_error_result["step_id"] == "stop_point"
    assert stops_config_error_result["handler"] == "tfl"
    assert stops_config_error_result["errors"] == {"base": "invalid_stop_point"}
    assert stops_config_error_result["data_schema"] == STEP_STOP_POINTS_DATA_SCHEMA


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    user_form_init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tfl.config_flow.call_tfl_api",
        side_effect=InvalidAuth,
    ):
        user_form_error_result = await hass.config_entries.flow.async_configure(
            user_form_init_result["flow_id"],
            user_input={
                CONF_API_APP_KEY: "appy_appy_app_key",
            },
        )

    assert user_form_error_result["type"] == FlowResultType.FORM
    assert user_form_error_result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    user_form_init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tfl.config_flow.call_tfl_api",
        side_effect=CannotConnect,
    ):
        user_form_error_result = await hass.config_entries.flow.async_configure(
            user_form_init_result["flow_id"],
            user_input={CONF_API_APP_KEY: "appy_appy_app_key"},
        )

    assert user_form_error_result["type"] == FlowResultType.FORM
    assert user_form_error_result["errors"] == {"base": "cannot_connect"}


async def setup_config_entry_and_add_to_hass(
    hass: HomeAssistant,
) -> config_entries.ConfigEntry:
    """Create the config entry and add it to hass."""
    data = {CONF_API_APP_KEY: "appy_appy_app_key"}
    options = {CONF_STOP_POINTS: ["AAAAAAAA1"]}
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="unique_id", data=data, options=options
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
