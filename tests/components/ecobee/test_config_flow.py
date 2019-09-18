"""Tests for the ecobee config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.ecobee import config_flow
from homeassistant.const import CONF_API_KEY

from homeassistant.components.ecobee.const import CONF_REFRESH_TOKEN


async def test_abort_if_already_setup(hass):
    """Test we abort if ecobee is already setup."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass

    with patch.object(hass.config_entries, "async_entries", return_value=[{}]):
        result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "one_instance_only"


async def test_full_flow_implementation(hass):
    """Test full ecobee flow works."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch("config_flow.Ecobee") as mock_ecobee:
        mock_ecobee.get_pin.return_value = True
        mock_ecobee.pin = "test_pin"
        result = await flow.async_step_user(user_input={CONF_API_KEY: "abcdef123456"})

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "authorize"
        assert result["description_placeholders"] == {"pin": "test_pin"}

        mock_ecobee.get_tokens.return_value = True
        mock_ecobee.refresh_token = "reftoken"

        result = await flow.async_step_authorize(user_input={})

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"]["title"] == "ecobee"
        assert result["data"][CONF_API_KEY] == "abcdef123456"
        assert result["data"][CONF_REFRESH_TOKEN] == "reftoken"
