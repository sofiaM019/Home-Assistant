"""
Support for KNX/IP sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.knx/
"""
import asyncio
import voluptuous as vol

from homeassistant.components.knx import DATA_KNX, ATTR_DISCOVER_DEVICES
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'address'
CONF_TYPE = 'type'

DEFAULT_NAME = 'KNX Sensor'
DEPENDENCIES = ['knx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TYPE): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, add_devices,
                         discovery_info=None):
    """Set up sensor(s) for KNX platform."""
    if DATA_KNX not in hass.data \
            or not hass.data[DATA_KNX].initialized:
        return False

    if discovery_info is not None:
        add_devices_from_component(hass, discovery_info, add_devices)
    else:
        add_devices_from_platform(hass, config, add_devices)

    return True


def add_devices_from_component(hass, discovery_info, add_devices):
    """Set up sensors for KNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXSensor(hass, device))
    add_devices(entities)


def add_devices_from_platform(hass, config, add_devices):
    """Set up sensor for KNX platform configured within plattform."""
    import xknx
    sensor = xknx.devices.Sensor(
        hass.data[DATA_KNX].xknx,
        name=config.get(CONF_NAME),
        group_address=config.get(CONF_ADDRESS),
        value_type=config.get(CONF_TYPE))
    hass.data[DATA_KNX].xknx.devices.add(sensor)
    add_devices([KNXSensor(hass, sensor)])


class KNXSensor(Entity):
    """Representation of a KNX sensor."""

    def __init__(self, hass, device):
        """Initialization of KNXSensor."""
        self.device = device
        self.hass = hass
        self.register_callbacks()

    def register_callbacks(self):
        """Register callbacks to update hass after device was changed."""
        @asyncio.coroutine
        def after_update_callback(device):
            """Callback after device was updated."""
            # pylint: disable=unused-argument
            yield from self.async_update_ha_state()
        self.device.register_device_updated_cb(after_update_callback)

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self.device.name

    @property
    def should_poll(self):
        """No polling needed within KNX."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device.resolve_state()

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self.device.unit_of_measurement()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return None
