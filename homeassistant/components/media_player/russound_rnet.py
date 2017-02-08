"""
Support for interfacing with Russound via RNET Protocol.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.russound_rnet/
"""

import logging
import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON, CONF_NAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = [
    'https://github.com/laf/russound/archive/0.1.7.zip'
    '#russound==0.1.7']

_LOGGER = logging.getLogger(__name__)

CONF_ZONES = 'zones'
CONF_SOURCES = 'sources'

SUPPORT_RUSSOUND = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
                   SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

SOURCE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Required(CONF_ZONES): vol.Schema({cv.positive_int: ZONE_SCHEMA}),
    vol.Required(CONF_SOURCES): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Russound RNET platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    if host is None or port is None:
        _LOGGER.error("Invalid config. Expected %s and %s",
                      CONF_HOST, CONF_PORT)
        return False

    from russound import russound

    russ = russound.Russound(host, port)
    russ.connect()

    sources = []
    for source in config[CONF_SOURCES]:
        sources.append(source['name'])

    if russ.is_connected():
        for zone_id, extra in config[CONF_ZONES].items():
            add_devices([RussoundRNETDevice(
                hass, russ, sources, zone_id, extra)])
    else:
        _LOGGER.error('Not connected to %s:%s', host, port)


class RussoundRNETDevice(MediaPlayerDevice):
    """Representation of a Russound RNET device."""

    def __init__(self, hass, russ, sources, zone_id, extra):
        """Initialise the Russound RNET device."""
        self._name = extra['name']
        self._russ = russ
        self._sources = sources
        self._zone_id = zone_id

        self._state = None
        self._volume = None
        self._source = None

        self.update()

    def update(self):
        """Retrieve latest state."""

        if self._russ.get_power('1', self._zone_id) == 0:
            self._state = STATE_OFF
        else:
            self._state = STATE_ON

        self._volume = self._russ.get_volume('1', self._zone_id) / 100.0

        # Returns 0 based index for source.
        index = self._russ.get_source('1', self._zone_id)
        # Possibility exists that user has defined list of all sources.
        # If a source is set externally that is beyond the defined list then
        # an exception will be thrown.
        # In this case return and unknown source (None)
        try:
            self._source = self._sources[index]
        except IndexError:
            self._source = None

    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the state of the device. directly from the device."""
        return self._state

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_RUSSOUND

    @property
    def source(self):
        """Get the currently selected source."""
        return self._source

    @property
    def volume_level(self):
        """Volume level of the media player (0..1).

        Value is returned based on a range (0..100).
        Therefore float divide by 100 to get to the required range.
        """
        return self._volume

    def set_volume_level(self, volume):
        """Set volume level.  Volume has a range (0..1).

        Translate this to a range of (0..100) as expected expected
        by _russ.set_volume()
        """
        self._russ.set_volume('1', self._zone_id, volume * 100)

    def turn_on(self):
        """Turn the media player on."""
        self._russ.set_power('1', self._zone_id, '1')

    def turn_off(self):
        """Turn off media player."""
        self._russ.set_power('1', self._zone_id, '0')

    def mute_volume(self, mute):
        """Send mute command."""
        self._russ.toggle_mute('1', self._zone_id)

    def select_source(self, source):
        """Set the input source."""
        if source in self._sources:
            index = self._sources.index(source)
            # 0 based value for source
            self._russ.set_source('1', self._zone_id, index)

    @property
    def source_list(self):
        """List of available input sources."""
        return self._sources
