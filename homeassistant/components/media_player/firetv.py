"""
Support for functionality to interact with FireTV devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.firetv/
"""
import functools
import logging
import threading
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE, SUPPORT_STOP,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, DOMAIN)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, STATE_IDLE, STATE_OFF, STATE_PAUSED,
    STATE_PLAYING, STATE_STANDBY, ATTR_ENTITY_ID)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['firetv==1.0.7']

_LOGGER = logging.getLogger(__name__)

SUPPORT_FIRETV = SUPPORT_PAUSE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_NEXT_TRACK | SUPPORT_SELECT_SOURCE | SUPPORT_STOP | \
    SUPPORT_PLAY

CONF_ADBKEY = 'adbkey'
CONF_GET_SOURCE = 'get_source'
CONF_GET_SOURCES = 'get_sources'

DEFAULT_NAME = 'Amazon Fire TV'
DEFAULT_PORT = 5555
DEFAULT_GET_SOURCE = True
DEFAULT_GET_SOURCES = True

FIRETV_KEY_POWER = 'POWER'
FIRETV_KEY_SLEEP = 'SLEEP'
FIRETV_KEY_HOME = 'HOME'
FIRETV_KEY_UP = 'UP'
FIRETV_KEY_DOWN = 'DOWN'
FIRETV_KEY_LEFT = 'LEFT'
FIRETV_KEY_RIGHT = 'RIGHT'
FIRETV_KEY_ENTER = 'ENTER'
FIRETV_KEY_BACK = 'BACK'
FIRETV_KEY_SPACE = 'SPACE'
FIRETV_KEY_MENU = 'MENU'

KEY_SERVICE = 'firetv_key'

ATTR_KEY = 'key'

SERVICE_KEY_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_KEY): cv.string,
})

DATA_KEY = '{}.firetv'.format(DOMAIN)


def has_adb_files(value):
    """Check that ADB key files exist."""
    priv_key = value
    pub_key = '{}.pub'.format(value)
    cv.isfile(pub_key)
    return cv.isfile(priv_key)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_ADBKEY): has_adb_files,
    vol.Optional(CONF_GET_SOURCE, default=DEFAULT_GET_SOURCE): cv.boolean,
    vol.Optional(CONF_GET_SOURCES, default=DEFAULT_GET_SOURCES): cv.boolean
})

PACKAGE_LAUNCHER = "com.amazon.tv.launcher"
PACKAGE_SETTINGS = "com.amazon.tv.settings"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the FireTV platform."""
    from firetv import FireTV

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = '{0}:{1}'.format(config[CONF_HOST], config[CONF_PORT])

    if CONF_ADBKEY in config:
        ftv = FireTV(host, config[CONF_ADBKEY])
        adb_log = " using adbkey='{0}'".format(config[CONF_ADBKEY])
    else:
        ftv = FireTV(host)
        adb_log = ""

    if not ftv.available:
        _LOGGER.warning("Could not connect to Fire TV at %s%s", host, adb_log)
        return

    name = config[CONF_NAME]
    get_source = config[CONF_GET_SOURCE]
    get_sources = config[CONF_GET_SOURCES]

    if host in hass.data[DATA_KEY]:
        _LOGGER.warning("Platform already setup on %s, skipping.", host)
    else:
        device = FireTVDevice(ftv, name, get_source, get_sources)
        add_entities([device])
        _LOGGER.debug("Setup Fire TV at %s%s", host, adb_log)
        hass.data[DATA_KEY][host] = device

    def service_key(service):
        """Dispatch service calls to target entities."""
        key = service.data.get(ATTR_KEY)
        entity_id = service.data.get(ATTR_ENTITY_ID)
        target_devices = [dev for dev in hass.data[DATA_KEY].values()
                          if dev.entity_id in entity_id]

        for target_device in target_devices:
            if key == FIRETV_KEY_POWER:
                target_device.firetv.power()
            elif key == FIRETV_KEY_SLEEP:
                target_device.firetv.sleep()
            elif key == FIRETV_KEY_HOME:
                target_device.firetv.home()
            elif key == FIRETV_KEY_UP:
                target_device.firetv.up()
            elif key == FIRETV_KEY_DOWN:
                target_device.firetv.down()
            elif key == FIRETV_KEY_LEFT:
                target_device.firetv.left()
            elif key == FIRETV_KEY_RIGHT:
                target_device.firetv.right()
            elif key == FIRETV_KEY_ENTER:
                target_device.firetv.enter()
            elif key == FIRETV_KEY_BACK:
                target_device.firetv.back()
            elif key == FIRETV_KEY_SPACE:
                target_device.firetv.space()
            elif key == FIRETV_KEY_MENU:
                target_device.firetv.menu()

    hass.services.register(
        DOMAIN, KEY_SERVICE, service_key, schema=SERVICE_KEY_SCHEMA)


def adb_decorator(override_available=False):
    """Send an ADB command if the device is available and not locked."""
    def adb_wrapper(func):
        """Wait if previous ADB commands haven't finished."""
        @functools.wraps(func)
        def _adb_wrapper(self, *args, **kwargs):
            # If the device is unavailable, don't do anything
            if not self.available and not override_available:
                return None

            # If an ADB command is already running, skip this command
            if not self.adb_lock.acquire(blocking=False):
                _LOGGER.info("Skipping an ADB command because a previous "
                             "command is still running")
                return None

            # Additional ADB commands will be prevented while trying this one
            try:
                returns = func(self, *args, **kwargs)
            except self.exceptions as err:
                _LOGGER.error(
                    "Failed to execute an ADB command. ADB connection re-"
                    "establishing attempt in the next update. Error: %s", err)
                returns = None
                self._available = False  # pylint: disable=protected-access
            finally:
                self.adb_lock.release()

            return returns

        return _adb_wrapper

    return adb_wrapper


class FireTVDevice(MediaPlayerDevice):
    """Representation of an Amazon Fire TV device on the network."""

    def __init__(self, ftv, name, get_source, get_sources):
        """Initialize the FireTV device."""
        from adb.adb_protocol import (
            InvalidChecksumError, InvalidCommandError, InvalidResponseError)

        self.firetv = ftv

        self._name = name
        self._get_source = get_source
        self._get_sources = get_sources

        # whether or not the ADB connection is currently in use
        self.adb_lock = threading.Lock()

        # ADB exceptions to catch
        self.exceptions = (
            AttributeError, BrokenPipeError, TypeError, ValueError,
            InvalidChecksumError, InvalidCommandError, InvalidResponseError)

        self._state = None
        self._available = self.firetv.available
        self._current_app = None
        self._running_apps = None

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_FIRETV

    @property
    def state(self):
        """Return the state of the player."""
        return self._state

    @property
    def available(self):
        """Return whether or not the ADB connection is valid."""
        return self._available

    @property
    def app_id(self):
        """Return the current app."""
        return self._current_app

    @property
    def source(self):
        """Return the current app."""
        return self._current_app

    @property
    def source_list(self):
        """Return a list of running apps."""
        return self._running_apps

    @adb_decorator(override_available=True)
    def update(self):
        """Get the latest date and update device state."""
        # Check if device is disconnected.
        if not self._available:
            self._running_apps = None
            self._current_app = None

            # Try to connect
            self.firetv.connect()
            self._available = self.firetv.available

        # If the ADB connection is not intact, don't update.
        if not self._available:
            return

        # Check if device is off.
        if not self.firetv.screen_on:
            self._state = STATE_OFF
            self._running_apps = None
            self._current_app = None

        # Check if screen saver is on.
        elif not self.firetv.awake:
            self._state = STATE_IDLE
            self._running_apps = None
            self._current_app = None

        else:
            # Get the running apps.
            if self._get_sources:
                self._running_apps = self.firetv.running_apps

            # Get the current app.
            if self._get_source:
                current_app = self.firetv.current_app
                if isinstance(current_app, dict)\
                        and 'package' in current_app:
                    self._current_app = current_app['package']
                else:
                    self._current_app = current_app

                # Show the current app as the only running app.
                if not self._get_sources:
                    if self._current_app:
                        self._running_apps = [self._current_app]
                    else:
                        self._running_apps = None

                # Check if the launcher is active.
                if self._current_app in [PACKAGE_LAUNCHER, PACKAGE_SETTINGS]:
                    self._state = STATE_STANDBY

                # Check for a wake lock (device is playing).
                elif self.firetv.wake_lock:
                    self._state = STATE_PLAYING

                # Otherwise, device is paused.
                else:
                    self._state = STATE_PAUSED

            # Don't get the current app.
            elif self.firetv.wake_lock:
                # Check for a wake lock (device is playing).
                self._state = STATE_PLAYING
            else:
                # Assume the devices is on standby.
                self._state = STATE_STANDBY

    @adb_decorator()
    def turn_on(self):
        """Turn on the device."""
        self.firetv.turn_on()

    @adb_decorator()
    def turn_off(self):
        """Turn off the device."""
        self.firetv.turn_off()

    @adb_decorator()
    def media_play(self):
        """Send play command."""
        self.firetv.media_play()

    @adb_decorator()
    def media_pause(self):
        """Send pause command."""
        self.firetv.media_pause()

    @adb_decorator()
    def media_play_pause(self):
        """Send play/pause command."""
        self.firetv.media_play_pause()

    @adb_decorator()
    def media_stop(self):
        """Send stop (back) command."""
        self.firetv.back()

    @adb_decorator()
    def volume_up(self):
        """Send volume up command."""
        self.firetv.volume_up()

    @adb_decorator()
    def volume_down(self):
        """Send volume down command."""
        self.firetv.volume_down()

    @adb_decorator()
    def media_previous_track(self):
        """Send previous track command (results in rewind)."""
        self.firetv.media_previous()

    @adb_decorator()
    def media_next_track(self):
        """Send next track command (results in fast-forward)."""
        self.firetv.media_next()

    @adb_decorator()
    def select_source(self, source):
        """Select input source.

        If the source starts with a '!', then it will close the app instead of
        opening it.
        """
        if isinstance(source, str):
            if not source.startswith('!'):
                self.firetv.launch_app(source)
            else:
                self.firetv.stop_app(source[1:].lstrip())
