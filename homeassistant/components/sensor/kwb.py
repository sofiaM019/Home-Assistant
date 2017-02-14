"""
Support for KWB Easyfire.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.kwb/
"""
import logging

import voluptuous as vol

from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_DEVICE
                                 , EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv


REQUIREMENTS = ['pykwb==0.0.5']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 23
DEFAULT_TYPE = 'tcp'
DEFAULT_RAW = False
DEFAULT_DEVICE = '/dev/ttyUSB0'

MODE_SERIAL = 0
MODE_TCP = 1

CONF_TYPE = 'type'
CONF_RAW = 'raw'

"""
SERIAL_SCHEMA = {
    vol.Required(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
    vol.Required(CONF_TYPE, default=DEFAULT_TYPE): 'serial',
    vol.Optional(CONF_RAW, default=DEFAULT_RAW): cv.boolean,
}

ETHERNET_SCHEMA = {
    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_TYPE, default=DEFAULT_TYPE): 'tcp',
    vol.Optional(CONF_RAW, default=DEFAULT_RAW): cv.boolean,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    DOMAIN: vol.Any(SERIAL_SCHEMA, ETHERNET_SCHEMA)
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Any(SERIAL_SCHEMA, ETHERNET_SCHEMA)
}, extra=vol.ALLOW_EXTRA)
"""

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TYPE, default=DEFAULT_TYPE): 'tcp',
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
    vol.Optional(CONF_RAW, default=DEFAULT_RAW): cv.boolean,
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the KWB component."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    device = config.get(CONF_DEVICE)
    connection_type = config.get(CONF_TYPE)
    raw = config.get(CONF_RAW)

    if raw == 'on':
        raw = True

    from pykwb import kwb

    _LOGGER.info('initializing')

    if connection_type == 'serial':
        easyfire = kwb.KWBEasyfire(MODE_SERIAL, "", 0, device)
    elif connection_type == 'tcp':
        easyfire = kwb.KWBEasyfire(MODE_TCP, host, port)
    else:
        return False

    sensors = []
    for sensor in easyfire.get_sensors():
        if ((sensor.sensor_type != kwb.PROP_SENSOR_RAW)
                or (sensor.sensor_type == kwb.PROP_SENSOR_RAW and raw)):
            sensors.append(KWBSensor(easyfire, sensor))

    add_devices(sensors)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                         lambda event: easyfire.stop_thread())

    _LOGGER.info('starting thread')
    easyfire.run_thread()
    _LOGGER.info('thread started')


class KWBSensor(Entity):
    """Representation of a KWB Easyfire sensor."""

    def __init__(self, easyfire, sensor):
        """Initialize the KWB sensor."""
        self._easyfire = easyfire
        self._sensor = sensor
        self._client_name = "KWB"
        self._name = self._sensor.name

    @property
    def name(self):
        """Return the name."""
        return '{} {}'.format(self._client_name, self._name)

    @property
    def state(self):
        """Return the state of value."""
        return self._sensor.value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._sensor.unit_of_measurement
