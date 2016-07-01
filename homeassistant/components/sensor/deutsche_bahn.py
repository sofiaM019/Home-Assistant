"""
Support for information about the German train system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.deutsche_bahn/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (CONF_PLATFORM)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['schiene==0.17']

CONF_START = 'from'
CONF_DESTINATION = 'to'
ICON = 'mdi:train'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'deutsche_bahn',
    vol.Required(CONF_START): cv.string,
    vol.Required(CONF_DESTINATION): cv.string,
})

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Deutsche Bahn Sensor."""
    start = config.get(CONF_START)
    destination = config.get(CONF_DESTINATION)

    add_devices([DeutscheBahnSensor(start, destination)])


# pylint: disable=too-few-public-methods
class DeutscheBahnSensor(Entity):
    """Implementation of a Deutsche Bahn sensor."""

    def __init__(self, start, goal):
        """Initialize the sensor."""
        self._name = start + ' to ' + goal
        self.data = SchieneData(start, goal)
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def state(self):
        """Return the departure time of the next train."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        connections = self.data.connections[0]
        connections['next'] = self.data.connections[1]['departure']
        connections['next_on'] = self.data.connections[2]['departure']
        return connections

    def update(self):
        """Get the latest delay from bahn.de and updates the state."""
        self.data.update()
        self._state = self.data.connections[0].get('departure', 'Unknown')
        if self.data.connections[0]['delay'] != 0:
            self._state += " + {}".format(self.data.connections[0]['delay'])


# pylint: disable=too-few-public-methods
class SchieneData(object):
    """Pull data from the bahn.de web page."""

    def __init__(self, start, goal):
        """Initialize the sensor."""
        import schiene
        self.start = start
        self.goal = goal
        self.schiene = schiene.Schiene()
        self.connections = [{}]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the connection data."""
        self.connections = self.schiene.connections(self.start, self.goal)

        for con in self.connections:
            # Detail info is not useful. Having a more consistent interface
            # simplifies usage of template sensors.
            if 'details' in con:
                con.pop('details')
                delay = con.get('delay', {'delay_departure': 0,
                                          'delay_arrival': 0})
                # IMHO only delay_departure is useful
                con['delay'] = delay['delay_departure']
                con['ontime'] = con.get('ontime', False)
