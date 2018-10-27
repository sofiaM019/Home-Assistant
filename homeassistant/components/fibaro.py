"""
Support for the Fibaro devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hive/
"""
import logging
from collections import defaultdict
import voluptuous as vol
import threading
from fiblary.client.v4.client import Client as FibaroClient
from homeassistant.const import (ATTR_ARMED, ATTR_BATTERY_LEVEL,
                                 ATTR_LAST_TRIP_TIME, ATTR_TRIPPED,
                                 EVENT_HOMEASSISTANT_STOP, CONF_PASSWORD, CONF_URL, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import convert, slugify
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

#REQUIREMENTS = ['pyhiveapi==0.2.14']

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'fibaro'
FIBARO_DEVICES = 'fibaro_devices'
FIBARO_SCENES = 'fibaro_scenes'
FIBARO_CONTROLLER = 'fibaro_controller'
FIBARO_ID_FORMAT = '{}_{}'
ATTR_CURRENT_POWER_W = "current_power_w"
ATTR_CURRENT_ENERGY_KWH = "current_energy_kwh"

FIBARO_COMPONENTS = [
    'binary_sensor',
    'sensor',
    'light',
    'switch',
    # 'lock',
    # 'climate',
    'cover',
    # 'scene'
]

FIBARO_TYPE_MAPPING = {
    'com.fibaro.temperatureSensor': 'sensor',
    'com.fibaro.multilevelSensor': "sensor",
    'com.fibaro.humiditySensor': 'sensor',
    'com.fibaro.binarySwitch': 'switch',
    'com.fibaro.FGRGBW441M': 'light',
    'com.fibaro.multilevelSwitch': 'switch',
    'com.fibaro.FGD212': 'light',
    'com.fibaro.FGRM222': 'cover',
    'com.fibaro.FGR': 'cover',
    'com.fibaro.doorSensor': 'binary_sensor',
    'com.fibaro.FGMS001v2': 'binary_sensor',
    'com.fibaro.lightSensor': 'sensor',
    'com.fibaro.seismometer': 'sensor',
    'com.fibaro.accelerometer': 'sensor',
    'com.fibaro.FGSS001': 'sensor',
    'com.fibaro.remoteSwitch': 'switch',
    'com.fibaro.sensor': 'sensor',
    'com.fibaro.colorController': 'sensor'
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_URL): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


class FibaroController(FibaroClient):
    """Initiate Fibaro Controller Class."""

    my_rooms = None
    my_devices = None
    my_fibaro_devices = None
    devices_lock = None
    callbacks = {}

    def __init__(self, hass, username, password, url):
        """Initialize the communication with the Fibaro controller."""
        self.devices_lock = threading.Lock()
        try:
            FibaroClient.__init__(self, url, username, password)
            my_info = self.info.get()
        except (Exception):
            _LOGGER.error("Failed to connect to Fibaro HC")
            raise ValueError('Failed to connect to Fibaro HC.')

        my_login = self.login.get()
        if my_login is None or my_login.status is False:
            _LOGGER.error("Invaid login for Fibaro HC. Please check username and password.")
            raise ValueError("Invaid login for Fibaro HC. Please check username and password.")

        self._read_rooms()
        self._read_devices()
        self.add_event_handler('value', self.value_change_handler)
        self.add_event_handler('value2', self.value2_change_handler)
        self.add_event_handler('Humidity', self.value_change_handler)
        self.add_event_handler('Pressure', self.value_change_handler)
        self.add_event_handler('Temperature', self.value_change_handler)
        self.add_event_handler('Wind', self.value_change_handler)
        self.add_event_handler('lastUpdated', self.lastUpdated_change_handler)
        self.add_event_handler('lastOutdoorUpdated', self.lastUpdated_change_handler)
        self.add_event_handler('log', self.log_handler)
        self.add_event_handler('ui.Current_Weather_Label.caption', self.log_handler)
        self.add_event_handler('power', self.power_change_handler)
        hass.data[FIBARO_CONTROLLER] = self
        hass.data[FIBARO_DEVICES] = self.my_fibaro_devices

    def value_change_handler(self, **kwargs):
        try:
            id = kwargs.get('id',None)
            v = kwargs.get('value',None)
            with self.devices_lock:
                self.my_devices[id].properties.value = v
            self.callbacks[id]()
        except:
            _LOGGER.error("Error updating value data")
        _LOGGER.info("Updated value: {}({}) to {}".format(self.get_device_name(self.my_devices[id]),id,v))

    def value2_change_handler(self, **kwargs):
        try:
            id = kwargs.get('id',None)
            v = kwargs.get('value',None)
            with self.devices_lock:
                self.my_devices[id].properties.value2 = v
            self.callbacks[id]()
        except:
            _LOGGER.error("Error updating value2 data")
        _LOGGER.info("Updated value2: {}({}) to {}".format(self.get_device_name(self.my_devices[id]),id,v))

    def log_handler(self, **kwargs):
        id = kwargs.get('id',None)
        v = kwargs.get('value',None)
        if v:
            _LOGGER.info("Fibaro {}: {}({}): {}".format(kwargs.get('property','unknown'),self.get_device_name(self.my_devices[id]),id,v))

    def lastUpdated_change_handler(self, **kwargs):
        pass

    def power_change_handler(self, **kwargs):
        pass

    def get_device_name(self, device):
        """Get room decorated name for Fibaro device."""
        if device.roomID == 0:
            room_name = 'Unknown'
        else:
            room_name = self.my_rooms[device.roomID].name
        device_name = room_name + '_' + device.name
        return device_name

    def register(self, device_id, callback):
        self.callbacks[device_id] = callback

    def _read_rooms(self):
        rooms = self.rooms.list()
        self.my_rooms = {}
        for room in rooms:
            self.my_rooms[room.id] = room
        return True

    def _read_devices(self):
        devices = self.devices.list()
        with self.devices_lock:
            self.my_devices = {}
            for device in devices:
                device.friendly_name = self.get_device_name(device)
                self.my_devices[device.id] = device
            if self.my_fibaro_devices is None:
                self.my_fibaro_devices = defaultdict(list)
            for _, device in self.my_devices.items():
                if (device.enabled is True) and (device.visible is True):
                    if device.type in FIBARO_TYPE_MAPPING:
                        device_type = FIBARO_TYPE_MAPPING[device.type]
                    elif device.baseType in FIBARO_TYPE_MAPPING:
                        device_type = FIBARO_TYPE_MAPPING[device.type]
                    else:
                        continue
                    if device_type is 'switch' and 'isLight' in device.properties and device.properties.isLight == 'true':
                        device_type = 'light'
                    device.mapped_type = device_type
                    self.my_fibaro_devices[device_type].append(device)
        return True


def setup(hass, config):
    """Set up the Fibaro Component."""

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    url = config[DOMAIN][CONF_URL]

    controller = FibaroController(hass, username, password, url)

    for component in FIBARO_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    controller.enable_state_handler()

    return True

class FibaroDevice(Entity):
    """Representation of a Fibaro device entity."""

    def __init__(self, fibaro_device, controller):
        """Initialize the device."""
        self.fibaro_device = fibaro_device
        self.controller = controller

        self._name = fibaro_device.friendly_name
        # Append device id to prevent name clashes in HA.
        self.ha_id = FIBARO_ID_FORMAT.format(
            slugify(self._name), fibaro_device.id)
        self.fibaro_device.ha_id = self.ha_id
        self.controller.register(fibaro_device.id, self._update_callback)

    def _update_callback(self):
        """Update the state."""
        self.schedule_update_ha_state(True)

    def get_level(self):
        """Get the level of Fibaro device."""
        if 'value' in self.fibaro_device.properties:
            return self.fibaro_device.properties.value
        return None

    def set_level(self, level):
        """Set the level of Fibaro device."""
        if 'setValue' in self.fibaro_device.actions:
            self.fibaro_device.setValue(level)
        else:
            _LOGGER.info("Not sure how to setValue: {} (available actions: {})".format(self.ha_id, self.fibaro_device.actions))

    def get_level2(self):
        """Get the tilt level of Fibaro device."""
        if 'value2' in self.fibaro_device.properties:
            return self.fibaro_device.properties.value2
        return None

    def set_level2(self, level):
        """Set the tilt level of Fibaro device."""
        if 'setValue2' in self.fibaro_device.actions:
            self.fibaro_device.setValue2(level)
        else:
            _LOGGER.info("Not sure how to setValue2: {} (available actions: {})".format(self.ha_id, self.fibaro_device.actions))

    def open(self):
        """Execute open command on Fibaro device."""
        if 'open' in self.fibaro_device.actions:
            self.fibaro_device.open()
        else:
            _LOGGER.info("Not sure how to open: {} (available actions: {})".format(self.ha_id, self.fibaro_device.actions))

    def close(self):
        """Execute close command on Fibaro device."""
        if 'close' in self.fibaro_device.actions:
            self.fibaro_device.close()
        else:
            _LOGGER.info("Not sure how to close: {} (available actions: {})".format(self.ha_id, self.fibaro_device.actions))

    def stop(self):
        """Execute stop command on Fibaro device."""
        if 'stop' in self.fibaro_device.actions:
            self.fibaro_device.stop()
        else:
            _LOGGER.info("Not sure how to stop: {} (available actions: {})".format(self.ha_id, self.fibaro_device.actions))

    def switch_on(self):
        """Switch on Fibaro device."""
        if 'turnOn' in self.fibaro_device.actions:
            self.fibaro_device.turnOn()
        else:
            _LOGGER.info("Not sure how to switch on: {} (available actions: {})".format(self.ha_id, self.fibaro_device.actions))

    def switch_off(self):
        """Switch off Fibaro device."""
        if 'turnOff' in self.fibaro_device.actions:
            self.fibaro_device.turnOff()
        else:
            _LOGGER.info("Not sure how to switch off: {} (available actions: {})".format(self.ha_id, self.fibaro_device.actions))

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        if 'power' in self.fibaro_device.properties:
            power = self.fibaro_device.properties.power
            if power:
                return convert(power, float, 0.0)
        else:
            return 0

    @property
    def current_binary_state(self):
        """Return the current binary state."""
        if self.fibaro_device.properties.value == 'false':
            return False
        if self.fibaro_device.properties.value == 'true':
            return True
        if int(self.fibaro_device.properties.value) > 0:
            return True
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Get polling requirement from fibaro device."""
#        return self.fibaro_device.should_poll
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        try:
            if 'battery' in self.fibaro_device.interfaces:
                attr[ATTR_BATTERY_LEVEL] = self.fibaro_device.properties.batteryLevel
        except:
            pass
        try:
            if 'fibaroAlarmArm' in self.fibaro_device.interfaces:
                armed = self.fibaro_device.properties.armed
                attr[ATTR_ARMED] = 'True' if armed else 'False'
        except:
            pass
        #
        # if self.fibaro_device.is_trippable:
        #     last_tripped = self.fibaro_device.last_trip
        #     if last_tripped is not None:
        #         utc_time = utc_from_timestamp(int(last_tripped))
        #         attr[ATTR_LAST_TRIP_TIME] = utc_time.isoformat()
        #     else:
        #         attr[ATTR_LAST_TRIP_TIME] = None
        #     tripped = self.fibaro_device.is_tripped
        #     attr[ATTR_TRIPPED] = 'True' if tripped else 'False'
        #
        try:
            if 'power' in self.fibaro_device.interfaces:
                power = float(self.fibaro_device.properties.power)
                if power:
                    attr[ATTR_CURRENT_POWER_W] = convert(power, float, 0.0)
        except:
            pass
        try:
            if 'energy' in self.fibaro_device.interfaces:
                energy = float(self.fibaro_device.properties.energy)
                if energy:
                    attr[ATTR_CURRENT_ENERGY_KWH] = convert(energy, float, 0.0)
        except:
            pass

        attr['Fibaro Device Id'] = self.fibaro_device.id
        attr['Id'] = self.ha_id

        return attr
