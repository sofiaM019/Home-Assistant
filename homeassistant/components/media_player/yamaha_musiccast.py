""" Example for configuration.yaml.

media_player:
  - platform: yamaha_musiccast
    name: "Living Room"
    host: 192.168.xxx.xx
    port: 5005

"""

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT,
    STATE_UNKNOWN, STATE_ON
)
from homeassistant.components.media_player import (
    MediaPlayerDevice, MEDIA_TYPE_MUSIC, PLATFORM_SCHEMA,
    SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_NEXT_TRACK,
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_PLAY,
    SUPPORT_VOLUME_SET, SUPPORT_VOLUME_MUTE,
    SUPPORT_SELECT_SOURCE, SUPPORT_STOP
)
_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = (
    SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_STOP |
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK |
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF |
    SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE |
    SUPPORT_SELECT_SOURCE
)

REQUIREMENTS = ['pymusiccast==0.0.6']

DEFAULT_NAME = "Yamaha Receiver"
DEFAULT_PORT = 5005

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Yamaha MusicCast platform."""
    import pymusiccast

    _LOGGER.debug("config: {} ({})".format(config, type(config)))

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    mcDevice = pymusiccast.mcDevice(host, udp_port=port)
    _LOGGER.debug("mcDevice: {} / UDP Port: {}".format(mcDevice, port))

    add_devices([YamahaDevice(mcDevice, name)], True)


class YamahaDevice(MediaPlayerDevice):
    """Representation of a Yamaha MusicCast device."""

    def __init__(self, mcDevice, name):
        """Initialize the Yamaha MusicCast device."""
        self._mcDevice = mcDevice
        self._name = name
        self._power = STATE_UNKNOWN
        self._volume = 0
        self._volumeMax = 0
        self._mute = False
        self._source = None
        self._source_list = []
        self._status = STATE_UNKNOWN
        self._media_status = None
        self._mcDevice.setYamahaDevice(self)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._power == STATE_ON and self._status is not STATE_UNKNOWN:
            return self._status
        else:
            return self._power

    @property
    def should_poll(self):
        """Push an update after each command."""
        return True

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def supported_features(self):
        """Flag of features that are supported."""
        return SUPPORTED_FEATURES

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def media_content_type(self):
        """Return the media content type."""
        if self._media_status is None:
            return None
        else:
            return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._media_status.media_duration \
            if self._media_status else None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._media_status.media_image_url \
            if self._media_status else None

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._media_status.media_artist if self._media_status else None

    @property
    def media_album(self):
        """Album of current playing media, music track only."""
        return self._media_status.media_album if self._media_status else None

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        return self._media_status.media_track if self._media_status else None

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._media_status.media_title if self._media_status else None

    def update(self):
        """Get the latest details from the device."""
        _LOGGER.debug("update: {}".format(self.entity_id))

        # call from constructor setup_platform()
        if not self.entity_id:
            _LOGGER.debug("First run")
            self._mcDevice.updateStatus(push=False)
        # call from regular polling
        else:
            # updateStatus_timer was set before
            if self._mcDevice.updateStatus_timer:
                _LOGGER.debug("is_alive: {}".format(
                    self._mcDevice.updateStatus_timer.is_alive()))
                # e.g. computer was suspended, while hass was running
                if not self._mcDevice.updateStatus_timer.is_alive():
                    _LOGGER.debug("Reinitializing")
                    self._mcDevice.updateStatus()

    def turn_on(self):
        """Turn on specified media player or all."""
        _LOGGER.debug("Turn device: on")
        self._mcDevice.setPower(True)

    def turn_off(self):
        """Turn off specified media player or all."""
        _LOGGER.debug("Turn device: off")
        self._mcDevice.setPower(False)

    def media_play(self):
        """Send the media player the command for play/pause."""
        _LOGGER.debug("Play")
        self._mcDevice.setPlayback("play")

    def media_pause(self):
        """Send the media player the command for pause."""
        _LOGGER.debug("Pause")
        self._mcDevice.setPlayback("pause")

    def media_stop(self):
        """Send the media player the stop command."""
        _LOGGER.debug("Stop")
        self._mcDevice.setPlayback("stop")

    def media_previous_track(self):
        """Send the media player the command for prev track."""
        _LOGGER.debug("Previous")
        self._mcDevice.setPlayback("previous")

    def media_next_track(self):
        """Send the media player the command for next track."""
        _LOGGER.debug("Next")
        self._mcDevice.setPlayback("next")

    def mute_volume(self, mute):
        """Send mute command."""
        _LOGGER.debug("Mute volume: {}".format(mute))
        self._mcDevice.setMute(mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        _LOGGER.debug("Volume level: {} / {}".format(
            volume, volume * self._volumeMax))
        self._mcDevice.setVolume(volume * self._volumeMax)

    def select_source(self, source):
        """Send the media player the command to select input source."""
        _LOGGER.debug("select_source: {}".format(source))
        self._status = STATE_UNKNOWN
        self._mcDevice.setInput(source)
