"""Platform to control a Zehnder ComfoAir 350 ventilation unit."""

import logging

from bitstring import BitArray

from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import DOMAIN, SIGNAL_COMFOAIR_UPDATE_RECEIVED, ComfoAirModule

_LOGGER = logging.getLogger(__name__)

ATTR_COMFORT_TEMPERATURE = "comfort_temperature"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"
ATTR_SUPPLY_TEMPERATURE = "supply_temperature"
ATTR_RETURN_TEMPERATURE = "return_temperature"
ATTR_EXHAUST_TEMPERATURE = "exhaust_temperature"
ATTR_AIR_FLOW_SUPPLY = "air_flow_supply"
ATTR_AIR_FLOW_EXHAUST = "air_flow_exhaust"
ATTR_FAN_SPEED_MODE = "speed_mode"

SENSOR_TYPES = {
    ATTR_COMFORT_TEMPERATURE: [
        "Comfort Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        0xD2,
        0 * 8,
        8,
    ],
    ATTR_OUTSIDE_TEMPERATURE: [
        "Outside Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        0xD2,
        1 * 8,
        8,
    ],
    ATTR_SUPPLY_TEMPERATURE: [
        "Supply Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        0xD2,
        2 * 8,
        8,
    ],
    ATTR_RETURN_TEMPERATURE: [
        "Return Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        0xD2,
        3 * 8,
        8,
    ],
    ATTR_EXHAUST_TEMPERATURE: [
        "Exhaust Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        0xD2,
        4 * 8,
        8,
    ],
    ATTR_AIR_FLOW_EXHAUST: ["Exhaust airflow", "%", "mdi:fan", 0xCE, 6 * 8, 8],
    ATTR_AIR_FLOW_SUPPLY: ["Supply airflow", "%", "mdi:fan", 0xCE, 7 * 8, 8],
    ATTR_FAN_SPEED_MODE: ["Speed mode", "", "mdi:fan", 0xCE, 8 * 8, 8],
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the ComfoAir sensor platform."""
    unit = hass.data[DOMAIN]

    sensors = []
    for resource in SENSOR_TYPES:
        sensors.append(
            ComfoAirSensor(
                name=f"{unit.name} {SENSOR_TYPES[resource][0]}",
                ca=unit,
                sensor_type=resource,
            )
        )

    async_add_entities(sensors, True)


class ComfoAirSensor(Entity):
    """Representation of a ComfoAir sensor."""

    def __init__(self, name, ca: ComfoAirModule, sensor_type) -> None:
        """Initialize the ComfoAir sensor."""
        self._ca = ca
        self._sensor_type = sensor_type
        self._unit = SENSOR_TYPES[self._sensor_type][1]
        self._icon = SENSOR_TYPES[self._sensor_type][2]
        self._sensor_id = SENSOR_TYPES[self._sensor_type][3]
        self._offset = SENSOR_TYPES[self._sensor_type][4]
        self._size = SENSOR_TYPES[self._sensor_type][5]
        self._name = name
        self._data = None

        data = self._ca[self._sensor_id]
        if data:
            self._update_state(data)

    def _update_state(self, data):
        bits = BitArray(data)
        value = bits[self._offset : self._offset + self._size].uint
        if self._unit == TEMP_CELSIUS:
            value = (value / 2) - 20
        self._data = value

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        @callback
        def async_handle_update(var):
            cmd, data = var
            if cmd == self._sensor_id:
                _LOGGER.debug("Dispatcher update for %#x: %s", cmd, data.hex())
                self._update_state(data)
                self.async_schedule_update_ha_state()

        # Register for dispatcher updates
        async_dispatcher_connect(
            self.hass, SIGNAL_COMFOAIR_UPDATE_RECEIVED, async_handle_update
        )

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def state(self):
        """Return the state of the entity."""
        return self._data

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit
