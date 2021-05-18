"""Platform for sensor integration."""
import logging

from boschshcpy import SHCBatteryDevice, SHCSession

from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
)

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the SHC sensor platform."""
    entities = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for sensor in session.device_helper.thermostats:
        entities.append(
            TemperatureSensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )
        entities.append(
            ValveTappetSensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    for sensor in session.device_helper.wallthermostats:
        entities.append(
            TemperatureSensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )
        entities.append(
            HumiditySensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    for sensor in session.device_helper.twinguards:
        entities.append(
            TemperatureSensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )
        entities.append(
            HumiditySensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )
        entities.append(
            PuritySensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )
        entities.append(
            AirQualitySensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    for sensor in session.device_helper.smart_plugs:
        entities.append(
            PowerSensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )
        entities.append(
            EnergySensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    for sensor in session.device_helper.smart_plugs_compact:
        entities.append(
            PowerSensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )
        entities.append(
            EnergySensor(
                device=sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    for sensor in (
        session.device_helper.smoke_detectors
        + session.device_helper.shutter_contacts
        + session.device_helper.universal_switches
        + session.device_helper.thermostats
        + session.device_helper.wallthermostats
        + session.device_helper.twinguards
    ):
        if sensor.supports_batterylevel:
            entities.append(
                BatterySensor(
                    device=sensor,
                    parent_id=session.information.unique_id,
                    entry_id=config_entry.entry_id,
                )
            )

    if entities:
        async_add_entities(entities)


class TemperatureSensor(SHCEntity):
    """Representation of a SHC temperature reporting sensor."""

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device.serial}_temperature"

    @property
    def name(self):
        """Return the name of this sensor."""
        return f"{self._device.name} Temperature"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.temperature

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return TEMP_CELSIUS


class HumiditySensor(SHCEntity):
    """Representation of a SHC humidity reporting sensor."""

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device.serial}_humidity"

    @property
    def name(self):
        """Return the name of this sensor."""
        return f"{self._device.name} Humidity"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.humidity

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return PERCENTAGE

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:water-percent"


class PuritySensor(SHCEntity):
    """Representation of a SHC purity reporting sensor."""

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device.serial}_purity"

    @property
    def name(self):
        """Return the name of this sensor."""
        return f"{self._device.name} Purity"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.purity

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return CONCENTRATION_PARTS_PER_MILLION

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:molecule-co2"


class AirQualitySensor(SHCEntity):
    """Representation of a SHC airquality reporting sensor."""

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device.serial}_airquality"

    @property
    def name(self):
        """Return the name of this sensor."""
        return f"{self._device.name} Air Quality"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.combined_rating.name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "rating_description": self._device.description,
            "temperature_rating": self._device.temperature_rating.name,
            "humidity_rating": self._device.humidity_rating.name,
            "purity_rating": self._device.purity_rating.name,
        }


class PowerSensor(SHCEntity):
    """Representation of a SHC power reporting sensor."""

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device.serial}_power"

    @property
    def name(self):
        """Return the name of this sensor."""
        return f"{self._device.name} Power"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.powerconsumption

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEVICE_CLASS_POWER

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return POWER_WATT

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:flash"


class EnergySensor(SHCEntity):
    """Representation of a SHC energy reporting sensor."""

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device.serial}_energy"

    @property
    def name(self):
        """Return the name of this sensor."""
        return f"{self._device.name} Energy"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.energyconsumption / 1000.0

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return ENERGY_KILO_WATT_HOUR

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:gauge"


class BatterySensor(SHCEntity):
    """Representation of a SHC battery reporting sensor."""

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device.serial}_battery"

    @property
    def name(self):
        """Return the name of this sensor."""
        return f"{self._device.name} Battery"

    @property
    def state(self):
        """Return the state of the sensor."""
        if (
            self._device.batterylevel
            == SHCBatteryDevice.BatteryLevelService.State.CRITICAL_LOW
        ):
            _LOGGER.warning("Battery state of device %s is critical low", self.name)
            return 0

        if (
            self._device.batterylevel
            == SHCBatteryDevice.BatteryLevelService.State.LOW_BATTERY
        ):
            _LOGGER.warning("Battery state of device %s is low", self.name)
            return 20

        if self._device.batterylevel == SHCBatteryDevice.BatteryLevelService.State.OK:
            return 100

        if (
            self._device.batterylevel
            == SHCBatteryDevice.BatteryLevelService.State.NOT_AVAILABLE
        ):
            _LOGGER.debug("Battery state of device %s is not available", self.name)

        return None

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return PERCENTAGE


class ValveTappetSensor(SHCEntity):
    """Representation of a SHC valve tappet reporting sensor."""

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device.serial}_valvetappet"

    @property
    def name(self):
        """Return the name of this sensor."""
        return f"{self._device.name} Valvetappet"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.position

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:gauge"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return PERCENTAGE

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "valve_tappet_state": self._device.valvestate.name,
        }
