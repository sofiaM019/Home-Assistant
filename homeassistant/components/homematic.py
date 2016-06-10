"""
Support for Homematic Devices.
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf

=======
>>>>>>> Added Homematic implementation
For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematic/

"""
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf

import logging
from collections import OrderedDict
from homeassistant.const import EVENT_HOMEASSISTANT_STOP,\
                                EVENT_PLATFORM_DISCOVERED,\
                                ATTR_SERVICE,\
                                ATTR_DISCOVERED
from homeassistant.loader import get_component
import homeassistant.bootstrap

DOMAIN = 'homematic'
REQUIREMENTS = ['pyhomematic==0.1.2']

# pylint: disable=wrong-import-position, wrong-import-order
import pyhomematic as HOMEMATIC

HOMEMATIC_DEVICES = {}

HA_HOMEMATIC_DEVICES = None
DEVICES_NOT_REGISTERED = []
=======
import logging
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE, ATTR_DISCOVERED 
from homeassistant.loader import get_component
import homeassistant.bootstrap
from collections import OrderedDict
    
DOMAIN = 'homematic'
REQUIREMENTS = ['pyhomematic==0.1.2']

import pyhomematic
homematic_devices = {}
HOMEMATIC = pyhomematic

HA_HOMEMATIC_DEVICES = None
devices_not_registered = []
>>>>>>> Added Homematic implementation

LOCAL_IP = "local_ip"
LOCAL_PORT = "local_port"
REMOTE_IP = "remote_ip"
REMOTE_PORT = "remote_port"
AUTODETECT = "autodetect"

DISCOVER_SWITCHES = "homematic.switch"
DISCOVER_LIGHTS = "homematic.light"
DISCOVER_SENSORS = "homematic.sensor"
DISCOVER_BINARY_SENSORS = "homematic.binary_sensor"
DISCOVER_ROLLERSHUTTER = "homematic.rollershutter"
DISCOVER_THERMOSTATS = "homematic.thermostat"

ATTR_DISCOVER_DEVICES = "devices"
ATTR_DISCOVER_CONFIG = "config"

HM_DEVICE_TYPES = {
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
    DISCOVER_SWITCHES: ['HMSwitch'],
    DISCOVER_LIGHTS: ['HMDimmer'],
    DISCOVER_SENSORS: ['HMCcu'],
    DISCOVER_THERMOSTATS: ['HMThermostat'],
    DISCOVER_BINARY_SENSORS: ['HMRemote', 'HMDoorContact'],
    DISCOVER_ROLLERSHUTTER: ['HMRollerShutter']
=======
   DISCOVER_SWITCHES: ['HMSwitch'],
   DISCOVER_LIGHTS: ['HMDimmer'],
   DISCOVER_SENSORS: ['HMCcu'],
   DISCOVER_THERMOSTATS: ['HMThermostat'],
   DISCOVER_BINARY_SENSORS: ['HMRemote', 'HMDoorContact'],
   DISCOVER_ROLLERSHUTTER: ['HMRollerShutter']
>>>>>>> Added Homematic implementation
}

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup(hass, config):
    """Setup the Homematic component."""
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
=======
    
    global homematic_devices, HOMEMATIC

>>>>>>> Added Homematic implementation
    local_ip = config[DOMAIN].get(LOCAL_IP)
    local_port = config[DOMAIN].get(LOCAL_PORT)
    remote_ip = config[DOMAIN].get(REMOTE_IP)
    remote_port = config[DOMAIN].get(REMOTE_PORT)
    autodetect = str(config[DOMAIN].get(AUTODETECT, False)).upper() == 'TRUE'
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf

    if local_ip is None or local_port is None or remote_ip is None or remote_port is None:
        _LOGGER.error("Missing required configuration item %s, %s, %s or %s",
                      LOCAL_IP, LOCAL_PORT, REMOTE_IP, REMOTE_PORT)
        return

    # Only required because there is no access on created entities and I lack the knowledge on
    # a better way how to make the devices variable accessible in all homematic components

    def system_callback_handler(src, *args):
        """Callback handler."""
        if src == 'newDevices':
            # pylint: disable=unused-variable
=======
    
    if local_ip is None or local_port is None or remote_ip is None or remote_port is None: 
        _LOGGER.error("Missing required configuration item %s, %s, %s or %s",
                     LOCAL_IP, LOCAL_PORT, REMOTE_IP, REMOTE_PORT)
        return

    # Only required because there is no access on created entities and I lack the knowledge on 
    # a better way how to make the devices variable accessible in all homematic components

    def system_callback_handler(src, *args):

        if src == 'newDevices':
>>>>>>> Added Homematic implementation
            (interface_id, dev_descriptions) = args
            key_dict = {}
            # Get list of all keys of the devices (ignoring channels)
            for dev in dev_descriptions:
                key_dict[dev['ADDRESS'].split(':')[0]] = True
            # Connect devices already created in HA to pyhomematic and add remaining devices to list
            devices_not_created = []
            for dev in key_dict:
                try:
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
                    if dev in HOMEMATIC_DEVICES:
                        for channel in HOMEMATIC_DEVICES[dev]:
                            channel.connect_to_homematic()
                    else:
                        devices_not_created.append(dev)
                # pylint: disable=broad-except
                except Exception as err:
                    # pylint: disable=logging-not-lazy
                    _LOGGER.error("Failed to setup device %s: %s" % ((str(dev), str(err))))
            # If configuration allows auto detection of devices,
            # all devices not configured are added.
=======
                    if dev in homematic_devices:
                        for channel in homematic_devices[dev]:
                            channel.connect_to_homematic()
                    else:
                        devices_not_created.append(dev)
                except Exception as err:
                    _LOGGER.error("Failed to setup device %s: %s" % (str(dev), str(err)))
            # If configuration allows auto detection of devices all devices not configured are added.         
>>>>>>> Added Homematic implementation
            if autodetect and devices_not_created:
                for component_name, func_get_devices, discovery_type in (
                        ('switch', get_switches, DISCOVER_SWITCHES),
                        ('light', get_lights, DISCOVER_LIGHTS),
                        ('rollershutter', get_rollershutters, DISCOVER_ROLLERSHUTTER),
                        ('binary_sensor', get_binary_sensors, DISCOVER_BINARY_SENSORS),
                        ('sensor', get_sensors, DISCOVER_SENSORS),
                        ('thermostat', get_thermostats, DISCOVER_THERMOSTATS)):
                    # Get all devices of a specific type
                    found_devices = func_get_devices(devices_not_created)
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf

=======
                    
>>>>>>> Added Homematic implementation
                    # Devices of this type are found they are setup in HA and a event is fired
                    if found_devices:
                        component = get_component(component_name)
                        config = {component.DOMAIN: found_devices}
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf

                        # Ensure component is loaded
                        homeassistant.bootstrap.setup_component(hass, component.DOMAIN, config)

                        # Fire discovery event
                        hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                            ATTR_SERVICE: discovery_type,
                            ATTR_DISCOVERED: {ATTR_DISCOVER_DEVICES: found_devices,
                                              ATTR_DISCOVER_CONFIG: ''}}
                                     )
                for dev in devices_not_created:
                    if dev in HOMEMATIC_DEVICES:
                        HOMEMATIC_DEVICES[dev].connect_to_homematic()

=======
            
                        # Ensure component is loaded
                        homeassistant.bootstrap.setup_component(hass, component.DOMAIN, config)
            
                        # Fire discovery event
                        hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                                      ATTR_SERVICE: discovery_type,
                                      ATTR_DISCOVERED: {ATTR_DISCOVER_DEVICES: found_devices,
                                                        ATTR_DISCOVER_CONFIG: ''}}
                                      )
                for dev in devices_not_created:
                    if dev in homematic_devices:
                        homematic_devices[dev].connect_to_homematic()
    
>>>>>>> Added Homematic implementation
    # Create server thread
    HOMEMATIC.create_server(local=local_ip,
                            localport=local_port,
                            remote=remote_ip,
                            remoteport=remote_port,
                            systemcallback=system_callback_handler,
                            interface_id='homeassistant')
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
    # Start server thread, connect to homegear, initialize to receive events
    HOMEMATIC.start()

    # Stops server when Homeassistant is shuting down
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, HOMEMATIC.stop)
    hass.config.components.append(DOMAIN)

=======
    HOMEMATIC.start() # Start server thread, connect to homegear, initialize to receive events
    # while not pyhomematic.devices or pyhomematic._server.working:
    #     time.sleep(1)
    # print('Homematic Devices found: ', len(HOMEMATIC.devices))
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, HOMEMATIC.stop) # Stops server when Homeassistant is shuting down
    hass.config.components.append(DOMAIN)
    
>>>>>>> Added Homematic implementation
    # if not autodetect:
    #    return True

    return True


def get_switches(keys=None):
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
    """Get switches."""
=======
>>>>>>> Added Homematic implementation
    return get_devices(HM_DEVICE_TYPES[DISCOVER_SWITCHES], keys)


def get_lights(keys=None):
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
    """Get lights."""
=======
>>>>>>> Added Homematic implementation
    return get_devices(HM_DEVICE_TYPES[DISCOVER_LIGHTS], keys)


def get_rollershutters(keys=None):
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
    """Get rollershutters."""
=======
>>>>>>> Added Homematic implementation
    return get_devices(HM_DEVICE_TYPES[DISCOVER_ROLLERSHUTTER], keys)


def get_binary_sensors(keys=None):
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
    """Get binary sensors."""
=======
>>>>>>> Added Homematic implementation
    return get_devices(HM_DEVICE_TYPES[DISCOVER_BINARY_SENSORS], keys)


def get_sensors(keys=None):
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
    """Get sensors."""
=======
>>>>>>> Added Homematic implementation
    return get_devices(HM_DEVICE_TYPES[DISCOVER_SENSORS], keys)


def get_thermostats(keys=None):
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
    """Get thermostats."""
=======
>>>>>>> Added Homematic implementation
    return get_devices(HM_DEVICE_TYPES[DISCOVER_THERMOSTATS], keys)


def get_devices(device_types, keys):
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
    """Get devices."""
=======
    global HOMEMATIC
    
>>>>>>> Added Homematic implementation
    device_arr = []
    if not keys:
        keys = HOMEMATIC.devices
    for key in keys:
        if HOMEMATIC.devices[key].__class__.__name__ in device_types:
            ordered_device_dict = OrderedDict()
            ordered_device_dict['platform'] = 'homematic'
            ordered_device_dict['key'] = key
            ordered_device_dict['name'] = HOMEMATIC.devices[key].NAME
            device_arr.append(ordered_device_dict)
    return device_arr


<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
def setup_hmdevice_entity_helper(hmdevicetype, config, add_callback_devices):
    """Helper to setup Homematic devices."""
    if HOMEMATIC.Server is None:
=======
def setup_hmdevice_entity_helper(HMDeviceType, config, add_callback_devices):
    global devices
    
    if pyhomematic.Server is None:
>>>>>>> Added Homematic implementation
        _LOGGER.error('Error setting up Homematic Device: Homematic server not configured.')
        return False
    address = config.get('address', None)
    if address is None:
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
        _LOGGER.error("Error setting up Device '%s': 'address' missing in configuration.", address)
        return False
    new_device = hmdevicetype(config)
    if address not in HOMEMATIC_DEVICES:
        HOMEMATIC_DEVICES[address] = []
    HOMEMATIC_DEVICES[address].append(new_device)
    add_callback_devices([new_device])
=======
        _LOGGER.error("Error setting up Homematic Device '%s': 'address' missing in configuration." % address)
        return False
    new_device = HMDeviceType(config)
    if address not in homematic_devices:
        homematic_devices[address] = []
    homematic_devices[address].append(new_device)
    add_callback_devices([new_device])        
>>>>>>> Added Homematic implementation
    return True


class HMDevice:
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
    """Homematic device base object."""

=======
>>>>>>> Added Homematic implementation
    def __init__(self, config):
        """Initialize generic HM device."""
        self._config = config
        self._address = config.get('address', None)
        self._name = config.get('name', None)
        if not self._name:
            self._name = self._address
        self._state = None
        self._hmdevice = None
        # TODO: Check if _is_connected can be replaced by the usage of _hmdevice
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
        self._is_connected = False
        self._is_available = False

    def connect_to_homematic(self):
        """Connect to Homematic."""
=======
        self._is_connected = False        
        self._is_available = False
    
    def connect_to_homematic(self):
        global HOMEMATIC
        
>>>>>>> Added Homematic implementation
        if self._address in HOMEMATIC.devices:
            self._hmdevice = HOMEMATIC.devices[self._address]
            self._is_connected = True
            self._is_available = not self._hmdevice.UNREACH

    @property
    def should_poll(self):
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
        """Return False as Homematic states are pushed by the XML RPC Server."""
        return False

=======
        """Returns False as Homematic states are pushed by the XML RPC Server"""
        return False
    
>>>>>>> Added Homematic implementation
    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the light."""
        return not self.available

    @property
    def available(self):
        """Return True if light is available."""
        return self._is_available
