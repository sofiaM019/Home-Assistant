"""Support for V2C sensors."""
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from requests import RequestException
from v2ctrydan import modbus_trydan

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHARGE_ENERGY_KEY,
    CHARGE_POWER_KEY,
    CHARGE_STATE_KEY,
    CHARGE_STATES,
    CHARGE_TIME_KEY,
    CONTRACTED_POWER_READ_KEY,
    DYNAMIC_POWER_MODE,
    DYNAMIC_POWER_MODE_READ_KEY,
    DYNAMIC_READ_KEY,
    FV_POWER_KEY,
    HOUSE_POWER_KEY,
    INTENSITY_READ_KEY,
    LOCK_READ_KEY,
    MAX_INTENSITY_READ_KEY,
    MIN_INTENSITY_READ_KEY,
    OCPP_READ_KEY,
    PAUSE_DAYNAMIC,
    PAUSE_DYNAMIC_READ_KEY,
    PAUSE_STATE_READ_KEY,
    PAYMENT_READ_KEY,
    PROMGRAM_READ_KEY,
    PWM_VALUE_KEY,
    SLAVE_ERROR,
    SLAVE_ERROR_KEY,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class SensorEntityDescriptionV2C(SensorEntityDescription):
    """Class describing sensor entities."""

    func: Callable[["SensorEntityDescriptionV2C"], Any] = None
    value: Any = None


TRYDAN_SENSOR_TYPES: tuple[SensorEntityDescriptionV2C, ...] = (
    SensorEntityDescriptionV2C(
        key=CHARGE_STATE_KEY,
        name="Charge State",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ev-station",
        value="0",
        func=lambda self: CHARGE_STATES[int(self.charger.getChargeState())],
    ),
    SensorEntityDescriptionV2C(
        key=CHARGE_ENERGY_KEY,
        name="Charge Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        value="0",
        func=lambda self: int(self.charger.getChargeEnergy()),
    ),
    SensorEntityDescriptionV2C(
        key=INTENSITY_READ_KEY,
        name="Intensity",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value="0",
        func=lambda self: int(self.charger.getIntensity()),
    ),
    SensorEntityDescriptionV2C(
        key=CHARGE_POWER_KEY,
        name="Charge Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value="0",
        func=lambda self: int(self.charger.getChargePower()),
    ),
    SensorEntityDescriptionV2C(
        key=SLAVE_ERROR_KEY,
        name="Slave Error",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:message-alert",
        value="0",
        func=lambda self: SLAVE_ERROR[int(self.charger.getSlaveError())],
    ),
    SensorEntityDescriptionV2C(
        key=CHARGE_TIME_KEY,
        name="Charge Time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:home-clock-outline",
        value="0",
        func=lambda self: int(self.charger.getChargeTime()),
    ),
    SensorEntityDescriptionV2C(
        key=PWM_VALUE_KEY,
        name="ADC PWM value",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal-variant",
        value="0",
        func=lambda self: int(self.charger.getValuePWM()),
    ),
    SensorEntityDescriptionV2C(
        key=HOUSE_POWER_KEY,
        name="House Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value="0",
        func=lambda self: int(self.charger.getHousePower()),
    ),
    SensorEntityDescriptionV2C(
        key=FV_POWER_KEY,
        name="PV Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value="0",
        func=lambda self: int(self.charger.getPowerFV()),
    ),
    SensorEntityDescriptionV2C(
        key=PAUSE_STATE_READ_KEY,
        name="Pause State",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:pause-circle-outline",
        value="0",
        func=lambda self: int(self.charger.getPauseState()),
    ),
    SensorEntityDescriptionV2C(
        key=LOCK_READ_KEY,
        name="Lock",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lock",
        value="0",
        func=lambda self: int(self.charger.getLock()),
    ),
    SensorEntityDescriptionV2C(
        key=PROMGRAM_READ_KEY,
        name="Program",
        state_class=SensorStateClass.MEASUREMENT,
        value="0",
        func=lambda self: int(self.charger.getPromgram()),
    ),
    SensorEntityDescriptionV2C(
        key=DYNAMIC_READ_KEY,
        name="Dynamic",
        state_class=SensorStateClass.MEASUREMENT,
        value="0",
        func=lambda self: int(self.charger.getDynamic()),
    ),
    SensorEntityDescriptionV2C(
        key=PAYMENT_READ_KEY,
        name="Payment",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:credit-card-outline",
        value="0",
        func=lambda self: int(self.charger.getPayment()),
    ),
    SensorEntityDescriptionV2C(
        key=OCPP_READ_KEY,
        name="Ocpp",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:car-electric-outline",
        value="0",
        func=lambda self: int(self.charger.getOCPP()),
    ),
    SensorEntityDescriptionV2C(
        key=MIN_INTENSITY_READ_KEY,
        name="Minimum Intensity",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chevron-triple-down",
        value="0",
        func=lambda self: int(self.charger.getMinIntensity()),
    ),
    SensorEntityDescriptionV2C(
        key=MAX_INTENSITY_READ_KEY,
        name="Maximum Intensity",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chevron-triple-up",
        value="0",
        func=lambda self: int(self.charger.getMaxIntensity()),
    ),
    SensorEntityDescriptionV2C(
        key=PAUSE_DYNAMIC_READ_KEY,
        name="Pause Dynamic state",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:play-pause",
        value="0",
        func=lambda self: PAUSE_DAYNAMIC[int(self.charger.getPauseDynamic())],  # cosas
    ),
    SensorEntityDescriptionV2C(
        key=DYNAMIC_POWER_MODE_READ_KEY,
        name="Dynamic Power",
        state_class=SensorStateClass.MEASUREMENT,
        value="0",
        func=lambda self: DYNAMIC_POWER_MODE[int(self.charger.getDynamicPowerMode())],
    ),
    SensorEntityDescriptionV2C(
        key=CONTRACTED_POWER_READ_KEY,
        name="Contractedd Power state",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        value="0",
        func=lambda self: "Inaccesible or unavailable"
        if self.charger.getContractedPower() == -1.0
        else self.charger.getContractedPower(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the v2c sensor."""
    host = config_entry.data[CONF_HOST]
    charger = modbus_trydan.Charger(host)
    entities = [SensorV2C(charger, description) for description in TRYDAN_SENSOR_TYPES]
    async_add_entities(entities)


class SensorV2C(SensorEntity):
    """Impleentation of an V2C sensor."""

    def __init__(self, charger, description: SensorEntityDescriptionV2C) -> None:
        """Initialize the V2C sensor."""
        self.entity_description = description
        self.charger = charger
        self.value = self.entity_description.value

    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        return self.value

    def update(self) -> None:
        """Get the monitored data from the charger."""
        try:
            self.value = self.entity_description.func(self)

        except (RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)
