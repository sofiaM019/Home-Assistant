import asyncio
import xknx
import voluptuous as vol

from homeassistant.components.xknx import DATA_XKNX, XKNXBinarySensor

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'address'
CONF_DEVICE_CLASS = 'device_class'
CONF_SIGNIFICANT_BIT = 'significant_bit'

DEFAULT_NAME = 'XKNX Binary Sensor'
DEPENDENCIES = ['xknx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): cv.string,
    vol.Optional(CONF_SIGNIFICANT_BIT, default=1): cv.positive_int,
})


@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, \
        discovery_info=None):
    """Setup the XKNX binary sensor platform."""
    if DATA_XKNX not in hass.data \
            or not hass.data[DATA_XKNX].initialized:
        return False

    if discovery_info is not None:
        yield from add_devices_from_component(hass, add_devices)
    else:
        yield from add_devices_from_platform(hass, config, add_devices)

    return True

@asyncio.coroutine
def add_devices_from_component(hass, add_devices):
    entities = []
    for device in hass.data[DATA_XKNX].xknx.devices:
        if isinstance(device, xknx.BinarySensor) and \
                not hasattr(device, "already_added_to_hass"):
            entities.append(XKNXBinarySensor(hass, device))
    add_devices(entities)

@asyncio.coroutine
def add_devices_from_platform(hass, config, add_devices):
    from xknx import BinarySensor
    binary_sensor = BinarySensor(hass.data[DATA_XKNX].xknx,
                                 name= \
                                     config.get(CONF_NAME),
                                 group_address= \
                                     config.get(CONF_ADDRESS),
                                 device_class= \
                                     config.get(CONF_DEVICE_CLASS),
                                 significant_bit= \
                                     config.get(CONF_SIGNIFICANT_BIT))
    binary_sensor.already_added_to_hass = True
    hass.data[DATA_XKNX].xknx.devices.add(binary_sensor)
    add_devices([XKNXBinarySensor(hass, binary_sensor)])
