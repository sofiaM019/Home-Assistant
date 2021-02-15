"""Asuswrt status sensors."""
import logging
from numbers import Number
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_GIGABYTES,
    DATA_RATE_MEGABITS_PER_SECOND,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    DATA_ASUSWRT,
    DOMAIN,
    SENSOR_CONNECTED_DEVICE,
    SENSOR_RX_BYTES,
    SENSOR_RX_RATES,
    SENSOR_TX_BYTES,
    SENSOR_TX_RATES,
)
from .router import AsusWrtRouter

DEFAULT_PREFIX = "Asuswrt"

SENSOR_DEVICE_CLASS = "device_class"
SENSOR_ICON = "icon"
SENSOR_NAME = "name"
SENSOR_UNIT = "unit"
SENSOR_FACTOR = "factor"
SENSOR_DEFAULT_ENABLED = "default_enabled"

UNIT_DEVICES = "Devices"

CONNECTION_SENSORS = {
    SENSOR_CONNECTED_DEVICE: {
        SENSOR_NAME: "Devices Connected",
        SENSOR_UNIT: UNIT_DEVICES,
        SENSOR_FACTOR: 0,
        SENSOR_ICON: "mdi:router-network",
        SENSOR_DEVICE_CLASS: None,
        SENSOR_DEFAULT_ENABLED: True,
    },
    SENSOR_RX_RATES: {
        SENSOR_NAME: "Download Speed",
        SENSOR_UNIT: DATA_RATE_MEGABITS_PER_SECOND,
        SENSOR_FACTOR: 125000,
        SENSOR_ICON: "mdi:download-network",
        SENSOR_DEVICE_CLASS: None,
    },
    SENSOR_TX_RATES: {
        SENSOR_NAME: "Upload Speed",
        SENSOR_UNIT: DATA_RATE_MEGABITS_PER_SECOND,
        SENSOR_FACTOR: 125000,
        SENSOR_ICON: "mdi:upload-network",
        SENSOR_DEVICE_CLASS: None,
    },
    SENSOR_RX_BYTES: {
        SENSOR_NAME: "Download",
        SENSOR_UNIT: DATA_GIGABYTES,
        SENSOR_FACTOR: 1000000000,
        SENSOR_ICON: "mdi:download",
        SENSOR_DEVICE_CLASS: None,
    },
    SENSOR_TX_BYTES: {
        SENSOR_NAME: "Upload",
        SENSOR_UNIT: DATA_GIGABYTES,
        SENSOR_FACTOR: 1000000000,
        SENSOR_ICON: "mdi:upload",
        SENSOR_DEVICE_CLASS: None,
    },
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensors."""
    router = hass.data[DOMAIN][entry.entry_id][DATA_ASUSWRT]
    entities = []

    for sensor_key in CONNECTION_SENSORS:
        entities.append(
            AsusWrtSensor(router, sensor_key, CONNECTION_SENSORS[sensor_key])
        )

    async_add_entities(entities, True)


class AsusWrtSensor(Entity):
    """Representation of a AsusWrt sensor."""

    def __init__(
        self, router: AsusWrtRouter, sensor_type: str, sensor: Dict[str, any]
    ) -> None:
        """Initialize a AsusWrt sensor."""
        self._state = None
        self._router = router
        self._sensor_type = sensor_type
        self._name = f"{DEFAULT_PREFIX} {sensor[SENSOR_NAME]}"
        self._unique_id = f"{DOMAIN} {self._name}"
        self._unit = sensor[SENSOR_UNIT]
        self._factor = sensor[SENSOR_FACTOR]
        self._icon = sensor[SENSOR_ICON]
        self._device_class = sensor[SENSOR_DEVICE_CLASS]
        self._default_enabled = sensor.get(SENSOR_DEFAULT_ENABLED, False)

    @callback
    def async_update_state(self) -> None:
        """Update the AsusWrt sensor."""
        state = self._router.sensors[self._sensor_type].value
        if state is None:
            self._state = STATE_UNKNOWN
            return
        if self._factor and isinstance(state, Number):
            self._state = round(state / self._factor, 2)
        else:
            self._state = state

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._default_enabled

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit."""
        return self._unit

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def device_class(self) -> str:
        """Return the device_class."""
        return self._device_class

    @property
    def device_state_attributes(self) -> Dict[str, any]:
        """Return the attributes."""
        return {"hostname": self._router.host}

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return self._router.device_info

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._router.sensors[self._sensor_type].enable()
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_sensor_update,
                self.async_on_demand_update,
            )
        )

    async def async_will_remove_from_hass(self):
        """Call when entity is removed from hass."""
        self._router.sensors[self._sensor_type].disable()
