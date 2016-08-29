"""
Support for the Automatic platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.automatic/
"""
from datetime import timedelta
import logging
import re
import threading
import requests

import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle, datetime as dt_util

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=30)

CONF_CLIENT_ID = 'client_id'
CONF_SECRET = 'secret'
CONF_DEVICES = 'devices'

SCOPE = 'scope:location scope:vehicle:profile scope:user:profile scope:trip'

ATTR_ACCESS_TOKEN = 'access_token'
ATTR_EXPIRES_IN = 'expires_in'
ATTR_RESULTS = 'results'
ATTR_VEHICLE = 'vehicle'
ATTR_ENDED_AT = 'ended_at'
ATTR_END_LOCATION = 'end_location'

URL_AUTHORIZE = 'https://accounts.automatic.com/oauth/access_token/'
URL_VEHICLES = 'https://api.automatic.com/vehicle/'
URL_TRIPS = 'https://api.automatic.com/trip/'

_VEHICLE_ID_REGEX = re.compile(
    (URL_VEHICLES + '(.*)?[/]$').replace('/', r'\/'))

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_SECRET): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_DEVICES): vol.All(cv.ensure_list, [cv.string])
})


def setup_scanner(hass, config: dict, see):
    """Validate the configuration and return an Automatic scanner."""
    try:
        AutomaticDeviceScanner(config, see)
    except IOError:
        return False

    return True


# pylint: disable=too-many-instance-attributes
class AutomaticDeviceScanner(object):
    """A class representing an Automatic device."""

    def __init__(self, config: dict, see) -> None:
        """Initialize the automatic device scanner."""
        self._client_id = config.get(CONF_CLIENT_ID)
        self._secret = config.get(CONF_SECRET)
        self._user_name = config.get(CONF_USERNAME)
        self._password = config.get(CONF_PASSWORD)
        self._devices = config.get(CONF_DEVICES, None)
        self._headers = None
        self._access_token = None
        self._token_expires = dt_util.now()
        self.last_results = {}
        self.last_trips = {}
        self.lock = threading.Lock()
        self.see = see

        self.scan_devices()

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [item['id'] for item in self.last_results]

    def get_device_name(self, device):
        """Get the device name from id."""
        vehicle = [item['display_name'] for item in self.last_results
                   if item['id'] == device]

        return vehicle[0]

    def _get_access_token(self):
        """Get the access token from automatic."""
        if self._access_token is None or self._token_expires <= dt_util.now():
            data = {
                'username': self._user_name,
                'password': self._password,
                'client_id': self._client_id,
                'client_secret': self._secret,
                'grant_type': 'password',
                'scope': SCOPE
            }

            resp = requests.post(
                URL_AUTHORIZE,
                data=data)

            if resp.status_code != 200:
                raise IOError(resp.content)

            json = resp.json()

            self._access_token = json[ATTR_ACCESS_TOKEN]
            self._token_expires = dt_util.now() + timedelta(
                seconds=json[ATTR_EXPIRES_IN])

        self._headers = {
            'Authorization': 'Bearer {}'.format(self._access_token)
        }

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self) -> None:
        """Update the device info."""
        with self.lock:
            self._get_access_token()

            _LOGGER.info('Getting device states')
            response = requests.get(URL_VEHICLES, headers=self._headers)

            if response.status_code != 200:
                raise IOError(response.content)

            self.last_results = [item for item in response.json()[ATTR_RESULTS]
                                 if self._devices is None or item[
                                     'display_name'] in self._devices]

            _LOGGER.info('Getting device trips')
            response = requests.get(URL_TRIPS, headers=self._headers)

            if response.status_code == 200:
                for trip in response.json()[ATTR_RESULTS]:
                    vehicle_id = _VEHICLE_ID_REGEX.match(
                        trip[ATTR_VEHICLE]).group(1)
                    if vehicle_id not in self.last_trips:
                        self.last_trips[vehicle_id] = trip
                    elif self.last_trips[vehicle_id][ATTR_ENDED_AT] < trip[
                            ATTR_ENDED_AT]:
                        self.last_trips[vehicle_id] = trip

            _LOGGER.info('Build device attributes')
            for vehicle in self.last_results:
                dev_id = vehicle.get('id')

                kwargs = {
                    'dev_id': dev_id,
                    'mac': dev_id,
                    'fuel_level': vehicle.get('fuel_level_percent')
                }

                if dev_id in self.last_trips:
                    end_location = self.last_trips[dev_id][ATTR_END_LOCATION]
                    kwargs['gps'] = (end_location['lat'], end_location['lon'])
                    kwargs['gps_accuracy'] = end_location['accuracy_m']

                self.see(**kwargs)
