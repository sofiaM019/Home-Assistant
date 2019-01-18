"""Test configuration and mocks for the SmartThings component."""
from collections import defaultdict
from unittest.mock import Mock, patch
from uuid import uuid4

from pysmartthings import (
    CLASSIFICATION_AUTOMATION, AppEntity, AppSettings, DeviceEntity,
    InstalledApp, Location)
import pytest

from homeassistant.components import webhook
from homeassistant.components.smartthings.const import (
    APP_NAME_PREFIX, CONF_APP_ID, CONF_INSTALLED_APP_ID, CONF_INSTANCE_ID,
    CONF_LOCATION_ID, DOMAIN, SETTINGS_INSTANCE_ID)
from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_PUSH, SOURCE_USER, ConfigEntry)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_WEBHOOK_ID
from homeassistant.setup import async_setup_component

from tests.common import mock_coro


@pytest.fixture(autouse=True)
async def setup_component(hass, config_file):
    """Load the SmartThing component."""
    with patch("os.path.isfile", return_value=True), \
        patch("homeassistant.components.smartthings.smartapp.load_json",
              return_value=config_file):
        await async_setup_component(hass, 'smartthings', {})
        hass.config.api.base_url = 'https://test.local'


def _create_location():
    loc = Location()
    loc.apply_data({
        'name': 'Test Location',
        'locationId': str(uuid4())
    })
    return loc


@pytest.fixture(name='location')
def location_fixture():
    """Fixture for a single location."""
    return _create_location()


@pytest.fixture(name='locations')
def locations_fixture(location):
    """Fixture for 2 locations."""
    return [location, _create_location()]


@pytest.fixture(name="app")
def app_fixture(hass, config_file):
    """Fixture for a single app."""
    app = AppEntity(Mock())
    app.apply_data({
        'appName': APP_NAME_PREFIX + str(uuid4()),
        'appId': str(uuid4()),
        'appType': 'WEBHOOK_SMART_APP',
        'classifications': [CLASSIFICATION_AUTOMATION],
        'displayName': 'Home Assistant',
        'description': "Home Assistant at " + hass.config.api.base_url,
        'singleInstance': True,
        'webhookSmartApp': {
            'targetUrl': webhook.async_generate_url(
                hass, hass.data[DOMAIN][CONF_WEBHOOK_ID]),
            'publicKey': ''}
    })
    app.refresh = Mock()
    app.refresh.return_value = mock_coro()
    app.save = Mock()
    app.save.return_value = mock_coro()
    settings = AppSettings(app.app_id)
    settings.settings[SETTINGS_INSTANCE_ID] = config_file[CONF_INSTANCE_ID]
    app.settings = Mock()
    app.settings.return_value = mock_coro(return_value=settings)
    return app


@pytest.fixture(name='app_settings')
def app_settings_fixture(app, config_file):
    """Fixture for an app settings."""
    settings = AppSettings(app.app_id)
    settings.settings[SETTINGS_INSTANCE_ID] = config_file[CONF_INSTANCE_ID]
    return settings


def _create_installed_app(location_id, app_id):
    item = InstalledApp()
    item.apply_data(defaultdict(str, {
        'installedAppId': str(uuid4()),
        'installedAppStatus': 'AUTHORIZED',
        'installedAppType': 'UNKNOWN',
        'appId': app_id,
        'locationId': location_id
    }))
    return item


@pytest.fixture(name='installed_app')
def installed_app_fixture(location, app):
    """Fixture for a single installed app."""
    return _create_installed_app(location.location_id, app.app_id)


@pytest.fixture(name='installed_apps')
def installed_apps_fixture(installed_app, locations, app):
    """Fixture for 2 installed apps."""
    return [installed_app,
            _create_installed_app(locations[1].location_id, app.app_id)]


@pytest.fixture(name='config_file')
def config_file_fixture():
    """Fixture representing the local config file contents."""
    return {
        CONF_INSTANCE_ID: str(uuid4()),
        CONF_WEBHOOK_ID: webhook.generate_secret()
    }


@pytest.fixture(name='smartthings_mock')
def smartthings_mock_fixture(locations):
    """Fixture to mock smartthings API calls."""
    def _location(location_id):
        return mock_coro(
            return_value=next(location for location in locations
                              if location.location_id == location_id))

    with patch("pysmartthings.SmartThings", autospec=True) as mock:
        mock.return_value.location.side_effect = _location
        yield mock


@pytest.fixture(name='device')
def device_fixture(location):
    """Fixture representing devices loaded."""
    item = DeviceEntity(None)
    item.status.refresh = Mock()
    item.status.refresh.return_value = mock_coro()
    item.apply_data({
        "deviceId": "743de49f-036f-4e9c-839a-2f89d57607db",
        "name": "GE In-Wall Smart Dimmer",
        "label": "Front Porch Lights",
        "deviceManufacturerCode": "0063-4944-3038",
        "locationId": location.location_id,
        "deviceTypeId": "8a9d4b1e3b9b1fe3013b9b206a7f000d",
        "deviceTypeName": "Dimmer Switch",
        "deviceNetworkType": "ZWAVE",
        "components": [
            {
                "id": "main",
                "capabilities": [
                    {
                        "id": "switch",
                        "version": 1
                    },
                    {
                        "id": "switchLevel",
                        "version": 1
                    },
                    {
                        "id": "refresh",
                        "version": 1
                    },
                    {
                        "id": "indicator",
                        "version": 1
                    },
                    {
                        "id": "sensor",
                        "version": 1
                    },
                    {
                        "id": "actuator",
                        "version": 1
                    },
                    {
                        "id": "healthCheck",
                        "version": 1
                    },
                    {
                        "id": "light",
                        "version": 1
                    }
                ]
            }
        ],
        "dth": {
            "deviceTypeId": "8a9d4b1e3b9b1fe3013b9b206a7f000d",
            "deviceTypeName": "Dimmer Switch",
            "deviceNetworkType": "ZWAVE",
            "completedSetup": False
        },
        "type": "DTH"
    })
    return item


@pytest.fixture(name='config_entry')
def config_entry_fixture(hass, installed_app, location):
    """Fixture representing a config entry."""
    data = {
        CONF_ACCESS_TOKEN: str(uuid4()),
        CONF_INSTALLED_APP_ID: installed_app.installed_app_id,
        CONF_APP_ID: installed_app.app_id,
        CONF_LOCATION_ID: location.location_id
    }
    return ConfigEntry("1", DOMAIN, location.name, data, SOURCE_USER,
                       CONN_CLASS_CLOUD_PUSH)


@pytest.fixture(name="device_factory")
def device_factory_fixture():
    """Fixture for creating mock devices."""
    def _factory(label, capabilities):
        device = Mock()
        device.label = label
        device.capabilities = capabilities
        device.device_id = uuid4()
        device.status = Mock()
        device.status.apply_attribute_update = Mock()
        return device
    return _factory


@pytest.fixture(name="event_factory")
def event_factory_fixture():
    """Fixture for creating mock devices."""
    def _factory(device_id, event_type="DEVICE_EVENT"):
        event = Mock()
        event.event_type = event_type
        event.device_id = device_id
        event.component_id = 'main'
        event.capability = ''
        event.attribute = ''
        event.value = ''
        return event
    return _factory


@pytest.fixture(name="event_request_factory")
def event_request_factory_fixture(event_factory):
    """Fixture for creating mock smartapp event requests."""
    def _factory(device_ids):
        request = Mock()
        request.installed_app_id = uuid4()
        request.events = [event_factory(id) for id in device_ids]
        request.events.append(event_factory(uuid4()))
        request.events.append(event_factory(device_ids[0], event_type="OTHER"))
        return request
    return _factory
