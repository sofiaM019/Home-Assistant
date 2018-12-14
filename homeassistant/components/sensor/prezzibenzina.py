"""
Support for the PrezziBenzina.it service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.prezzibenzina/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_TIME)
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['prezzibenzina-py==1.1.4']

_LOGGER = logging.getLogger(__name__)

ATTR_SERVICE = 'service'
ATTR_FUEL = 'fuel'

ATTRIBUTION = 'Data provided by PrezziBenzina.it'

CONF_STATION = 'station'

SCAN_INTERVAL = timedelta(minutes=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION): cv.string
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the PrezziBenzina platform."""
    from prezzibenzina import PrezziBenzinaPy

    station = config[CONF_STATION]

    client = PrezziBenzinaPy()
    dev = []
    info = client.get_by_id(station)
    name = client.get_station_name(station)

    for index, info in enumerate(info):
        dev.append(PrezziBenzinaSensor(index, 
                                       client, 
                                       station, 
                                       name, 
                                       info['fuel']))

    async_add_entities(dev, True)


class PrezziBenzinaSensor(Entity):
    """Implementation of a PrezziBenzina sensor."""

    def __init__(self, index, client, station, name, ft):
        """Initialize the sensor."""
        self._client = client
        self._index = index
        self._data = None
        self._station = station
        self._name = "{} {}".format(name, ft)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:fuel'

    @property
    def state(self):
        """Return the state of the device."""
        return self._data['price'].replace(" €", "")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._data['price'].split(" ")[1]

    @property
    def device_state_attributes(self):
        """Return the state attributes of the last update."""
        attrs = {
            ATTR_FUEL: self._data['fuel'],
            ATTR_SERVICE: self._data['service'],
            ATTR_TIME: self._data['date'],
            ATTR_ATTRIBUTION: ATTRIBUTION
        }
        return attrs

    async def async_update(self):
        """Get the latest data and updates the states."""
        self._data = self._client.get_by_id(self._station)[self._index]