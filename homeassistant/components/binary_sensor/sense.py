"""
Support for monitoring a Sense energy sensor device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.sense/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.sense import SENSE_DATA

REQUIREMENTS = ['sense']

_LOGGER = logging.getLogger(__name__)

BIN_SENSOR_CLASS = 'power'

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Sense sensor."""
    if SENSE_DATA not in hass.data:
        _LOGGER.error("Requires Sense component loaded")
        return False
    
    data = hass.data[SENSE_DATA]

    sense_devices = data.get_discovered_device_data()
    devices = [SenseDevice(data, device) for device in sense_devices]
    add_entities(devices)


class SenseDevice(BinarySensorDevice):
    """Implementation of a Sense energy device binary sensor."""

    def __init__(self, data, device):
        """Initialize the sensor."""
        self._name = device['name']
        self._id = device['id']
        self._icon = self.sense_to_mdi(device['icon'])
        self._data = data
        self._state = False

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name
        
    @property
    def unique_id(self):
        """Return the id of the binary sensor."""
        return self._id
        
    @property
    def icon(self):
        """Return the icon of the binary sensor."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return BIN_SENSOR_CLASS

    def update(self):
        """Retrieve latest state."""
        from sense_energy.sense_api import SenseAPITimeoutException
        try:
            self._data.get_realtime()
        except SenseAPITimeoutException:
            _LOGGER.error("Timeout retrieving data")
            return
        self._state = self._name in self._data.active_devices
        
    def sense_to_mdi(self, sense_icon):
        """Convert sense icon to mdi icon"""
        MDI_ICONS = {'ac' : 'air-conditioner',
                     'aquarium' : 'fish',
                     'car' : 'car-electric',
                     'computer' : 'desktop-classic',
                     'cup' : 'coffee',
                     'dehumidifier' : 'water-off',
                     'dishes' : 'dishwasher',
                     'drill' : 'toolbox',
                     'fan' : 'fan',
                     'freezer' : 'fridge-top',
                     'fridge' : 'fridge-bottom',
                     'game' : 'gamepad-variant',
                     'garage' : 'garage',
                     'grill' : 'stove',
                     'heat' : 'fire',
                     'heater' : 'radiatior',
                     'humidifier' : 'water',
                     'kettle' : 'kettle',
                     'leafblower' : 'leaf',
                     'lightbulb' : 'lightbulb',
                     'media_console' : 'set-top-box',
                     'modem' : 'router-wireless',
                     'outlet' : 'power-socket-us',
                     'papershredder' : 'shredder',
                     'printer' : 'printer',
                     'pump' : 'water-pump',
                     'settings' : 'settings',
                     'skillet' : 'pot',
                     'smartcamera' : 'webcam',
                     'socket' : 'power-plug',
                     'sound' : 'speaker',
                     'stove' : 'stove',
                     'trash' : 'trash-can',
                     'tv' : 'television',
                     'vacuum' : 'robot-vacuum',
                     'washer' : 'washing-machine'}
        return 'mdi-' + MDI_ICONS.get(sense_icon, 'power-plug')
