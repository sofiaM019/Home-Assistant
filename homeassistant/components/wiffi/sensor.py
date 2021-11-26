"""Sensor platform support for wiffi devices."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    ENTITY_CATEGORY_DIAGNOSTIC,
    PRESSURE_MBAR,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import WiffiEntity
from .const import CREATE_ENTITY_SIGNAL
from .wiffi_strings import (
    WIFFI_UOM_DEGREE,
    WIFFI_UOM_LUX,
    WIFFI_UOM_MILLI_BAR,
    WIFFI_UOM_PERCENT,
    WIFFI_UOM_TEMP_CELSIUS,
)

# map to determine HA device class from wiffi's unit of measurement
UOM_TO_DEVICE_CLASS_MAP = {
    WIFFI_UOM_TEMP_CELSIUS: SensorDeviceClass.TEMPERATURE,
    WIFFI_UOM_PERCENT: SensorDeviceClass.HUMIDITY,
    WIFFI_UOM_MILLI_BAR: SensorDeviceClass.PRESSURE,
    WIFFI_UOM_LUX: SensorDeviceClass.ILLUMINANCE,
}

# map to convert wiffi unit of measurements to common HA uom's
UOM_MAP = {
    WIFFI_UOM_DEGREE: DEGREE,
    WIFFI_UOM_TEMP_CELSIUS: TEMP_CELSIUS,
    WIFFI_UOM_MILLI_BAR: PRESSURE_MBAR,
}

# map to determine HA entity category from wiffi's entity name
NAME_TO_ENTITY_CAT = {
    "rssi": ENTITY_CATEGORY_DIAGNOSTIC,
    "uptime": ENTITY_CATEGORY_DIAGNOSTIC,
    "ssid": ENTITY_CATEGORY_DIAGNOSTIC,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up platform for a new integration.

    Called by the HA framework after async_forward_entry_setup has been called
    during initialization of a new integration (= wiffi).
    """

    @callback
    def _create_entity(device, metric):
        """Create platform specific entities."""
        entities = []

        if metric.is_number:
            entities.append(NumberEntity(device, metric, config_entry.options))
        elif metric.is_string:
            entities.append(StringEntity(device, metric, config_entry.options))

        async_add_entities(entities)

    async_dispatcher_connect(hass, CREATE_ENTITY_SIGNAL, _create_entity)


class NumberEntity(WiffiEntity, SensorEntity):
    """Entity for wiffi metrics which have a number value."""

    def __init__(self, device, metric, options):
        """Initialize the entity."""
        super().__init__(device, metric, options)
        self._attr_device_class = UOM_TO_DEVICE_CLASS_MAP.get(
            metric.unit_of_measurement
        )
        self._attr_entity_category = NAME_TO_ENTITY_CAT.get(self._name)
        self._unit_of_measurement = UOM_MAP.get(
            metric.unit_of_measurement, metric.unit_of_measurement
        )
        self._value = metric.value

        if self._is_measurement_entity():
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._is_metered_entity():
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        self.reset_expiration_date()

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @property
    def native_value(self):
        """Return the value of the entity."""
        return self._value

    @callback
    def _update_value_callback(self, device, metric):
        """Update the value of the entity.

        Called if a new message has been received from the wiffi device.
        """
        self.reset_expiration_date()
        self._unit_of_measurement = UOM_MAP.get(
            metric.unit_of_measurement, metric.unit_of_measurement
        )

        self._value = metric.value

        self.async_write_ha_state()


class StringEntity(WiffiEntity, SensorEntity):
    """Entity for wiffi metrics which have a string value."""

    def __init__(self, device, metric, options):
        """Initialize the entity."""
        super().__init__(device, metric, options)
        if self._name.endswith("_ip"):
            self._attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC
        else:
            self._attr_entity_category = NAME_TO_ENTITY_CAT.get(metric.description)
        self._value = metric.value
        self.reset_expiration_date()

    @property
    def native_value(self):
        """Return the value of the entity."""
        return self._value

    @callback
    def _update_value_callback(self, device, metric):
        """Update the value of the entity.

        Called if a new message has been received from the wiffi device.
        """
        self.reset_expiration_date()
        self._value = metric.value
        self.async_write_ha_state()
