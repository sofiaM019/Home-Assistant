import logging
import requests
import json
import time
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_API_KEY
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from datetime import datetime
_LOGGER = logging.getLogger(__name__)


DEPENDENCIES = []
REQUIREMENTS = ['pytz==2016.7']

CONF_HOST = 'host'
CONF_PORT = 'port'
CONF_DAYS = 'days'
CONF_INCLUDED = 'include_paths'
CONF_UNIT = 'unit'
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8989
DEFAULT_DAYS  = '1'
DEFAULT_UNIT = 'GB'

SENSOR_TYPES = {
        'diskspace': ['Disk Space', 'GB', 'mdi:harddisk'],
        'queue': ['Queue', 'Episodes', 'mdi:download'],
        'upcoming': ['Upcoming', 'Episodes', 'mdi:television'],
        'wanted': ['Wanted', 'Episodes', 'mdi:television'],
        'series': ['Series', 'Shows', 'mdi:television'],
        'commands': ['Commands', 'Commands', 'mdi:code-braces']
    }

ENDPOINTS = {
        'diskspace': 'http://{0}:{1}/api/diskspace?apikey={2}',
        'queue': 'http://{0}:{1}/api/queue?apikey={2}',
        'upcoming': 'http://{0}:{1}/api/calendar?apikey={2}&start={3}&end={4}',
        'wanted': 'http://{0}:{1}/api/wanted/missing?apikey={2}',
        'series': 'http://{0}:{1}/api/series?apikey={2}',
        'commands': 'http://{0}:{1}/api/command?apikey={2}'
        }

# Suport to Yottabytes for the future, why not
BYTE_SIZES = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(list(SENSOR_TYPES.keys()))]),
    vol.Optional(CONF_INCLUDED, default=[]): cv.ensure_list,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_DAYS, default=DEFAULT_DAYS): cv.string,
    vol.Optional(CONF_UNIT, default=DEFAULT_UNIT): vol.In(BYTE_SIZES)
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    add_devices([Sonarr(hass, config, sensor) for sensor in config[CONF_MONITORED_CONDITIONS]])
    return True

class Sonarr(Entity):
    def __init__(self, hass, conf, sensor_type):
        from pytz import timezone
        # Configuration data
        self.conf = conf
        self.host = conf.get(CONF_HOST)
        self.port = conf.get(CONF_PORT)
        self.apikey = conf.get(CONF_API_KEY)
        self.included = conf.get(CONF_INCLUDED)
        self.days = int(conf.get(CONF_DAYS))

        # Object data
        self.tz = timezone(str(hass.config.time_zone))
        self.type = sensor_type
        self._name = SENSOR_TYPES[self.type][0]
        if self.type == 'diskspace':
            self._unit = conf.get(CONF_UNIT)
        else:
            self._unit = SENSOR_TYPES[self.type][1]
        self._icon = SENSOR_TYPES[self.type][2]

        # Update sensor
        self.update()

    def update(self):
        start = self.getDate(self.tz)
        end = self.getDate(self.tz, self.days)
        res = requests.get(ENDPOINTS[self.type].format(self.host, self.port, self.apikey, start, end))
        if res.status_code == 200:
            if self.type in ['upcoming', 'queue', 'series', 'commands']:
                if self.days == 1 and self.type =='upcoming':
                    # Sonarr API returns empty array if start and end dates are the same
                    # So we need to filter to just today
                    self.data = list(filter(lambda x: x['airDate'] == str(start), res.json()))
                else:
                    self.data = res.json()
                self._state = len(self.data)
            elif self.type == 'wanted':
                data = res.json()
                res = requests.get('{}&pageSize={}'.format(
                    ENDPOINTS[self.type].format(self.host, self.port, self.apikey),
                    data['totalRecords']
                    ))
                self.data = res.json()['records']
                self._state = len(self.data)
            elif self.type =='diskspace':
                # If included paths are not provided, use all data
                if self.included == []:
                    self.data = res.json()
                else:
                    # Filter to only show lists that are included
                    self.data = list(filter(lambda x: x['path'] in self.included, res.json()))
                self._state = '{:.2f}'.format(self.toUnit(sum([data['freeSpace'] for data in self.data])))

    @property
    def name(self):
        return "{} {}".format("Sonarr", self._name)

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def device_state_attributes(self):
        attributes = {}
        if self.type == 'upcoming':
            for show in self.data:
                attributes[show['series']['title']] = 'S{:02d}E{:02d}'.format(show['seasonNumber'], show['episodeNumber'])
        elif self.type == 'queue':
            for show in self.data:
                attributes[show['series']['title'] + ' S{:02d}E{:02d}'.format(show['episode']['seasonNumber'], show['episode']['episodeNumber'])] = '{:.2f}%'.format(100*(1-(show['sizeleft']/show['size'])))
        elif self.type == 'wanted':
            for show in self.data:
                attributes[show['series']['title'] + ' S{:02d}E{:02d}'.format(show['seasonNumber'], show['episodeNumber'])] = show['airDate']
        elif self.type == 'commands':
            for command in self.data:
                attributes[command['name']] = command['state']
        elif self.type == 'diskspace':
            for data in self.data:
                attributes[data['path']] = '{:.2f}/{:.2f}{} ({:.2f}%)'.format(
                        self.toUnit(data['freeSpace']),
                        self.toUnit(data['totalSpace']),
                        self._unit,
                        (self.toUnit(data['freeSpace'])/self.toUnit(data['totalSpace'])*100)
                    )
        elif self.type == 'series':
            for show in self.data:
                attributes[show['title']] = '{}/{} Episodes'.format(show['episodeFileCount'], show['episodeCount'])
        return attributes

    @property
    def icon(self):
        return self._icon

    def getDate(self, zone, offset=0):
        day = 60*60*24
        return datetime.date(datetime.fromtimestamp(time.time() + day*offset, tz=zone))

    def toUnit(self, value):
        return value/1024**BYTE_SIZES.index(self._unit)
