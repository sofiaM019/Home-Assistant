"""Viessmann ViCare sensor device."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ViCareEntity, ViCareRequiredKeysMixin
from .const import (
    CONF_HEATING_TYPE,
    DOMAIN,
    HEATING_TYPE_TO_CREATOR_METHOD,
    VICARE_DEVICE_LIST,
    HeatingType,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ViCareBinarySensorEntityDescription(
    BinarySensorEntityDescription, ViCareRequiredKeysMixin
):
    """Describes ViCare binary sensor entity."""


CIRCUIT_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="circulationpump_active",
        name="Circulation pump active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getCirculationPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="frost_protection_active",
        name="Frost protection active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getFrostProtectionActive(),
    ),
)

BURNER_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="burner_active",
        name="Burner active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getActive(),
    ),
)

COMPRESSOR_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="compressor_active",
        name="Compressor active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getActive(),
    ),
)

GLOBAL_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key="solar_pump_active",
        name="Solar pump active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getSolarPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="charging_active",
        name="DHW Charging active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getDomesticHotWaterChargingActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="dhw_circulationpump_active",
        name="DHW Circulation Pump Active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getDomesticHotWaterCirculationPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key="dhw_pump_active",
        name="DHW Pump Active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getDomesticHotWaterPumpActive(),
    ),
)


def _build_entity(name, vicare_api, device_config, sensor, has_multiple_devices: bool):
    """Create a ViCare binary sensor entity."""
    try:
        sensor.value_getter(vicare_api)
        _LOGGER.debug("Found entity %s", name)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("Feature not supported %s", name)
        return None
    except AttributeError:
        _LOGGER.debug("Attribute Error %s", name)
        return None

    return ViCareBinarySensor(
        name,
        vicare_api,
        device_config,
        sensor,
        has_multiple_devices,
    )


async def _entities_from_descriptions(
    hass, entities, sensor_descriptions, iterables, device, has_multiple_devices
):
    """Create entities from descriptions and list of burners/circuits."""
    for description in sensor_descriptions:
        for current in iterables:
            suffix = ""
            if len(iterables) > 1:
                suffix = f" {current.id}"
            entity = await hass.async_add_executor_job(
                _build_entity,
                f"{description.name}{suffix}",
                current,
                device,
                description,
                has_multiple_devices,
            )
            if entity is not None:
                entities.append(entity)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare binary sensor devices."""
    entities = []
    has_multiple_devices = (
        len(hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_LIST]) > 1
    )
    for device in hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_LIST]:
        api = getattr(
            device,
            HEATING_TYPE_TO_CREATOR_METHOD[
                HeatingType(config_entry.data[CONF_HEATING_TYPE])
            ],
        )()
        for description in GLOBAL_SENSORS:
            entity = await hass.async_add_executor_job(
                _build_entity,
                f"{description.name}",
                api,
                device,
                description,
                has_multiple_devices,
            )
            if entity is not None:
                entities.append(entity)

        try:
            await _entities_from_descriptions(
                hass,
                entities,
                CIRCUIT_SENSORS,
                api.circuits,
                device,
                has_multiple_devices,
            )
        except PyViCareNotSupportedFeatureError:
            _LOGGER.info("No circuits found")

        try:
            await _entities_from_descriptions(
                hass,
                entities,
                BURNER_SENSORS,
                api.burners,
                device,
                has_multiple_devices,
            )
        except PyViCareNotSupportedFeatureError:
            _LOGGER.info("No burners found")

        try:
            await _entities_from_descriptions(
                hass,
                entities,
                COMPRESSOR_SENSORS,
                api.compressors,
                device,
                has_multiple_devices,
            )
        except PyViCareNotSupportedFeatureError:
            _LOGGER.info("No compressors found")

    async_add_entities(entities)


class ViCareBinarySensor(ViCareEntity, BinarySensorEntity):
    """Representation of a ViCare sensor."""

    _attr_has_entity_name = True
    entity_description: ViCareBinarySensorEntityDescription

    def __init__(
        self,
        name,
        api,
        device_config,
        description: ViCareBinarySensorEntityDescription,
        has_multiple_devices: bool,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = name
        self._api = api
        self.entity_description = description
        self._device_config = device_config
        ViCareEntity.__init__(self, device_config, has_multiple_devices)

    @property
    def available(self):
        """Return True if entity is available."""
        return self._attr_is_on is not None

    @property
    def unique_id(self) -> str:
        """Return unique ID for this device."""
        tmp_id = (
            f"{self._device_config.getConfig().serial}-{self.entity_description.key}"
        )
        if hasattr(self._api, "id"):
            return f"{tmp_id}-{self._api.id}"
        return tmp_id

    def update(self):
        """Update state of sensor."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_is_on = self.entity_description.value_getter(self._api)
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)
