"""
For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.tube-state
"""

import voluptuous as vol
import logging

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.util import Throttle

from datetime import datetime, timedelta
import requests
import json

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Powered by TfL Open Data"
CONF_LINE= 'line'
DOMAIN = 'tube_state'     #  must match the name of the compoenent
SCAN_INTERVAL = timedelta(minutes=1)
TUBE_LINES= [
    'Bakerloo',
    'Central',
    'Circle',
    'District',
    'Hammersmith & City',
    'Jubilee',
    'Metropolitan',
    'Northern',
    'Piccadilly',
    'Victoria',
    'Waterloo & City']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
    vol.Required(CONF_LINE): vol.In(TUBE_LINES)
    })
}, extra=vol.ALLOW_EXTRA)

def setup_platform(hass, config, add_devices, discovery_info=None):
    data = TubeData()
    data.update()
    sensors = []
    for line in config.get(CONF_LINE):
        sensors.append(LondonTubeSensor(line, data))

    add_devices(sensors, True)
    _LOGGER.info("The tube_state component is ready!")
    _LOGGER.info(ATTRIBUTION)

class LondonTubeSensor(Entity):
    """
    Sensor that reads the status of a line from TubeData.
    """
    ICON = 'mdi:subway'

    def __init__(self, name, data):
        """Initialize the sensor."""
        self._name = name
        self._data = data
        self._state = None
        self._description = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        attrs = {}
        attrs['Description'] = self._description
        return attrs

    def update(self):
        """Update the sensor."""
        self._data.update()
        self._state = self._data.data[self.name]['State']
        self._description = self._data.data[self.name]['Description']


class TubeData(object):
    """Get the latest tube data from TFL."""

    def __init__(self):
        """Initialize the TubeData object."""
        self.data = None

    # Update only once in scan interval.
    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from TFL."""
        URL = 'https://api.tfl.gov.uk/line/mode/tube/status'
        response = requests.get(URL)
        _LOGGER.info("TFL Request made")
        if response.status_code != 200:
            _LOGGER.warning("Invalid response from API")
        else:
            self.data = parse_API_response(response.json())

def parse_API_response(response):
    '''Take in the TFL API json response to
    https://api.tfl.gov.uk/line/mode/tube/status'''
    lines = [line['name'] for line in response]
    data_dict = dict.fromkeys(lines)

    for line in response:
        statuses = [status['statusSeverityDescription']
            for status in line['lineStatuses']]
        state = ' + '.join(sorted(set(statuses)))

        if state == 'Good Service':
            reason =  'Nothing to report'
        else:
            reason = ' *** '.join(
                [status['reason'] for status in line['lineStatuses']])

        attr = {'State': state, 'Description': reason}
        data_dict[line['name']] = attr

    return data_dict
