"""
Receive signals from a keyboard and use it as a remote control.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/keyboard_remote/
"""

# pylint: disable=import-error
import threading
import logging
import os
import time

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP
)

DOMAIN = "keyboard_remote"
REQUIREMENTS = ['evdev==0.6.1']
_LOGGER = logging.getLogger(__name__)
ICON = 'mdi:remote'
KEYBOARD_REMOTE_COMMAND_RECEIVED = 'keyboard_remote_command_received'
KEYBOARD_REMOTE_CONNECTED = 'keyboard_remote_connected'
KEYBOARD_REMOTE_DISCONNECTED = 'keyboard_remote_disconnected'
KEY_CODE = 'key_code'
KEY_VALUE = {'key_up': 0, 'key_down': 1, 'key_hold': 2}
TYPE = 'type'
DEVICE_DESCRIPTOR = 'device_descriptor'
DEVICE_NAME = 'device_name'
SECRET_GROUP = 'Device descriptor or name'


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Exclusive(DEVICE_DESCRIPTOR, SECRET_GROUP): cv.string,
        vol.Exclusive(DEVICE_NAME, SECRET_GROUP): cv.string,
        vol.Optional(TYPE, default='key_up'):
        vol.All(cv.string, vol.Any('key_up', 'key_down', 'key_hold')),
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup keyboard_remote."""
    config = config.get(DOMAIN)

    if not config.get(DEVICE_DESCRIPTOR) and\
       not config.get(DEVICE_NAME):
        _LOGGER.warn(
            'KeyboardRemote: Error: No device_descriptor\
             or device_name found.'
            )
        return

    keyboard_remote = KeyboardRemote(
        hass,
        config
    )

    def _start_keyboard_remote(_event):
        keyboard_remote.run()

    def _stop_keyboard_remote(_event):
        keyboard_remote.stopped.set()

    hass.bus.listen_once(
        EVENT_HOMEASSISTANT_START,
        _start_keyboard_remote
    )
    hass.bus.listen_once(
        EVENT_HOMEASSISTANT_STOP,
        _stop_keyboard_remote
    )

    return True


class KeyboardRemote(threading.Thread):
    """This interfaces with the inputdevice using evdev."""

    def __init__(self, hass, config):
        """Construct a KeyboardRemote interface object."""
        from evdev import InputDevice, list_devices

        self.device_descriptor = config.get(DEVICE_DESCRIPTOR)
        self.device_name = config.get(DEVICE_NAME)
        self.dev = self._get_keyboard_device()
        if self.dev is not None:
            _LOGGER.warn(
                'KeyboardRemote: keyboard connected'
                )
        else:
            id_folder = '/dev/input/by-id/'
            device_names = [InputDevice(file_name).name
                            for file_name in list_devices()]
            _LOGGER.warn(
                'KeyboardRemote: keyboard not connected.\
                Check /dev/input/event* permissions.\
                Possible device names are:\n %s.\n \
                Possible device descriptors are %s:\n %s',
                device_names,
                id_folder,
                os.listdir(id_folder)
                )

        threading.Thread.__init__(self)
        self.stopped = threading.Event()
        self.hass = hass
        self.key_value = KEY_VALUE.get(config.get(TYPE, 'key_up'))

    def _get_keyboard_device(self):
        from evdev import InputDevice, list_devices
        if self.device_name:
            devices = [InputDevice(file_name) for file_name in list_devices()]
            for device in devices:
                if self.device_name == device.name:
                    return device
        elif self.device_descriptor:
            try:
                device = InputDevice(self.device_descriptor)
            except OSError:  # Keyboard not present
                _LOGGER.debug(
                    'KeyboardRemote: keyboard not connected, %s',
                    self.device_descriptor)
                return None
            return device
        else:
            return None

    def run(self):
        """Main loop of the KeyboardRemote."""
        from evdev import categorize, ecodes

        if self.dev is not None:
            self.dev.grab()
            _LOGGER.debug(
                'KeyboardRemote interface started for %s',
                self.dev)

        while not self.stopped.isSet():
            # Sleeps to ease load on processor
            time.sleep(.1)

            if self.dev is None:
                self.dev = self._get_keyboard_device()
                if self.dev is not None:
                    self.dev.grab()
                    self.hass.bus.fire(
                        KEYBOARD_REMOTE_CONNECTED
                    )
                    _LOGGER.warn('KeyboardRemote: keyboard re-connected')
                else:
                    continue

            try:
                event = self.dev.read_one()
            except IOError:  # Keyboard Disconnected
                self.dev = None
                self.hass.bus.fire(
                    KEYBOARD_REMOTE_DISCONNECTED
                )
                _LOGGER.warn('KeyboardRemote: keyboard disconnected')
                continue

            if not event:
                continue

            # pylint: disable=no-member
            if event.type is ecodes.EV_KEY and event.value is self.key_value:
                _LOGGER.debug(categorize(event))
                self.hass.bus.fire(
                    KEYBOARD_REMOTE_COMMAND_RECEIVED,
                    {KEY_CODE: event.code}
                )
