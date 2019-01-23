"""Define tests for the Ambient PWS config flow."""
from aioambient.errors import AmbientError

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.ambient_station import (
    CONF_APP_KEY, DOMAIN, config_flow)
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry, MockDependency, mock_coro


@pytest.fixture
def get_devices_response():
    """Define a fixture for a successful /devices response."""
    return mock_coro()


@pytest.fixture
def mock_aioambient(get_devices_response):
    """Mock the aioambient library."""
    with MockDependency('aioambient') as mock_aioambient_:
        mock_aioambient_.Client(
        ).api.get_devices.return_value = get_devices_response
        yield mock_aioambient_


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_APP_KEY: '67890fghij',
    }

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.AmbientStationFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['errors'] == {CONF_APP_KEY: 'identifier_exists'}


@pytest.mark.parametrize(
    'get_devices_response', [mock_coro(exception=AmbientError)])
async def test_invalid_api_key(hass, mock_aioambient):
    """Test that an invalid API/App Key throws an error."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_APP_KEY: '67890fghij',
    }

    flow = config_flow.AmbientStationFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['errors'] == {CONF_APP_KEY: 'invalid_key'}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.AmbientStationFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'


async def test_step_import(hass, mock_aioambient):
    """Test that the import step works."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_APP_KEY: '67890fghij',
    }

    flow = config_flow.AmbientStationFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(import_config=conf)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '67890fghij'
    assert result['data'] == {
        CONF_API_KEY: '12345abcde',
        CONF_APP_KEY: '67890fghij',
    }


async def test_step_user(hass, mock_aioambient):
    """Test that the user step works."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_APP_KEY: '67890fghij',
    }

    flow = config_flow.AmbientStationFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '67890fghij'
    assert result['data'] == {
        CONF_API_KEY: '12345abcde',
        CONF_APP_KEY: '67890fghij',
    }
