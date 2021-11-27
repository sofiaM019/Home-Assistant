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
        super().__init__(device, metric, options, SensorEntityDescription)

        self.entity_description.device_class = UOM_TO_DEVICE_CLASS_MAP.get(
            metric.unit_of_measurement
        )
        self.entity_description.native_unit_of_measurement = UOM_MAP.get(
            metric.unit_of_measurement, metric.unit_of_measurement
        )
        if self._is_measurement_entity():
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._is_metered_entity():
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

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
        self.entity_description.unit_of_measurement = UOM_MAP.get(
            metric.unit_of_measurement, metric.unit_of_measurement
        )

        self._value = metric.value

        self.async_write_ha_state()


class StringEntity(WiffiEntity, SensorEntity):
    """Entity for wiffi metrics which have a string value."""

    def __init__(self, device, metric, options):
        """Initialize the entity."""
        super().__init__(device, metric, options, SensorEntityDescription)

        if self.entity_description.key.endswith("_ip"):
            self.entity_description.entity_category = ENTITY_CATEGORY_DIAGNOSTIC

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
