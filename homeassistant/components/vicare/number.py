"""Number for ViCare."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import logging
from typing import Any

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceComponent,
)
from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
from requests.exceptions import ConnectionError as RequestConnectionError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_LIST, DOMAIN, Program
from .entity import ViCareEntity
from .types import ViCareDevice, ViCareRequiredKeysMixin
from .utils import get_circuits, is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViCareNumberEntityDescription(NumberEntityDescription, ViCareRequiredKeysMixin):
    """Describes ViCare number entity."""

    value_getter: Callable[[PyViCareDevice], float]
    value_setter: Callable[[PyViCareDevice, float], Any] | None = None
    min_value_getter: Callable[[PyViCareDevice], float | None] | None = None
    max_value_getter: Callable[[PyViCareDevice], float | None] | None = None
    stepping_getter: Callable[[PyViCareDevice], float | None] | None = None


CIRCUIT_ENTITY_DESCRIPTIONS: tuple[ViCareNumberEntityDescription, ...] = (
    ViCareNumberEntityDescription(
        key="heating curve shift",
        translation_key="heating_curve_shift",
        icon="mdi:plus-minus-variant",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getHeatingCurveShift(),
        value_setter=lambda api, shift: (
            api.setHeatingCurve(shift, api.getHeatingCurveSlope())
        ),
        min_value_getter=lambda api: api.getHeatingCurveShiftMin(),
        max_value_getter=lambda api: api.getHeatingCurveShiftMax(),
        stepping_getter=lambda api: api.getHeatingCurveShiftStepping(),
        native_min_value=-13,
        native_max_value=40,
        native_step=1,
    ),
    ViCareNumberEntityDescription(
        key="heating curve slope",
        translation_key="heating_curve_slope",
        icon="mdi:slope-uphill",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getHeatingCurveSlope(),
        value_setter=lambda api, slope: (
            api.setHeatingCurve(api.getHeatingCurveShift(), slope)
        ),
        min_value_getter=lambda api: api.getHeatingCurveSlopeMin(),
        max_value_getter=lambda api: api.getHeatingCurveSlopeMax(),
        stepping_getter=lambda api: api.getHeatingCurveSlopeStepping(),
        native_min_value=0.2,
        native_max_value=3.5,
        native_step=0.1,
    ),
    ViCareNumberEntityDescription(
        key="normal_temperature",
        translation_key="normal_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(Program.NORMAL),
        value_setter=lambda api, value: api.setProgramTemperature(
            Program.NORMAL, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(Program.NORMAL),
        max_value_getter=lambda api: api.getProgramMaxTemperature(Program.NORMAL),
        stepping_getter=lambda api: api.getProgramStepping(Program.NORMAL),
    ),
    ViCareNumberEntityDescription(
        key="reduced_temperature",
        translation_key="reduced_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(Program.REDUCED),
        value_setter=lambda api, value: api.setProgramTemperature(
            Program.REDUCED, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(Program.REDUCED),
        max_value_getter=lambda api: api.getProgramMaxTemperature(Program.REDUCED),
        stepping_getter=lambda api: api.getProgramStepping(Program.REDUCED),
    ),
    ViCareNumberEntityDescription(
        key="comfort_temperature",
        translation_key="comfort_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(Program.COMFORT),
        value_setter=lambda api, value: api.setProgramTemperature(
            Program.COMFORT, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(Program.COMFORT),
        max_value_getter=lambda api: api.getProgramMaxTemperature(Program.COMFORT),
        stepping_getter=lambda api: api.getProgramStepping(Program.COMFORT),
    ),
    ViCareNumberEntityDescription(
        key="normal_heating_temperature",
        translation_key="normal_heating_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            Program.NORMAL_HEATING
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            Program.NORMAL_HEATING, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            Program.NORMAL_HEATING
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            Program.NORMAL_HEATING
        ),
        stepping_getter=lambda api: api.getProgramStepping(Program.NORMAL_HEATING),
    ),
    ViCareNumberEntityDescription(
        key="reduced_heating_temperature",
        translation_key="reduced_heating_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            Program.REDUCED_HEATING
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            Program.NORMAL_HEATING, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            Program.REDUCED_HEATING
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            Program.REDUCED_HEATING
        ),
        stepping_getter=lambda api: api.getProgramStepping(Program.REDUCED_HEATING),
    ),
    ViCareNumberEntityDescription(
        key="comfort_heating_temperature",
        translation_key="comfort_heating_temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDesiredTemperatureForProgram(
            Program.COMFORT_HEATING
        ),
        value_setter=lambda api, value: api.setProgramTemperature(
            Program.COMFORT_HEATING, value
        ),
        min_value_getter=lambda api: api.getProgramMinTemperature(
            Program.COMFORT_HEATING
        ),
        max_value_getter=lambda api: api.getProgramMaxTemperature(
            Program.COMFORT_HEATING
        ),
        stepping_getter=lambda api: api.getProgramStepping(Program.COMFORT_HEATING),
    ),
)


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareNumber]:
    """Create ViCare number entities for a device."""

    return [
        ViCareNumber(
            circuit,
            device.config,
            description,
        )
        for device in device_list
        for circuit in get_circuits(device.api)
        for description in CIRCUIT_ENTITY_DESCRIPTIONS
        if is_supported(description.key, description, circuit)
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare number devices."""
    device_list = hass.data[DOMAIN][config_entry.entry_id][DEVICE_LIST]

    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            device_list,
        )
    )


class ViCareNumber(ViCareEntity, NumberEntity):
    """Representation of a ViCare number."""

    entity_description: ViCareNumberEntityDescription

    def __init__(
        self,
        api: PyViCareHeatingDeviceComponent,
        device_config: PyViCareDeviceConfig,
        description: ViCareNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(device_config, api, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.value_setter:
            self.entity_description.value_setter(self._api, value)
        self.schedule_update_ha_state()

    def update(self) -> None:
        """Update state of number."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_native_value = self.entity_description.value_getter(
                    self._api
                )

                if min_value := _get_value(
                    self.entity_description.min_value_getter, self._api
                ):
                    self._attr_native_min_value = min_value

                if max_value := _get_value(
                    self.entity_description.max_value_getter, self._api
                ):
                    self._attr_native_max_value = max_value

                if stepping_value := _get_value(
                    self.entity_description.stepping_getter, self._api
                ):
                    self._attr_native_step = stepping_value
        except RequestConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)


def _get_value(
    fn: Callable[[PyViCareDevice], float | None] | None,
    api: PyViCareHeatingDeviceComponent,
) -> float | None:
    return None if fn is None else fn(api)
