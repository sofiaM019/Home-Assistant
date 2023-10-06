"""Viessmann ViCare button device."""
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

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ViCareEntity, ViCareRequiredKeysMixinWithSet
from .const import (
    CONF_HEATING_TYPE,
    DOMAIN,
    HEATING_TYPE_TO_CREATOR_METHOD,
    VICARE_DEVICE_LIST,
    HeatingType,
)

_LOGGER = logging.getLogger(__name__)

BUTTON_DHW_ACTIVATE_ONETIME_CHARGE = "activate_onetimecharge"


@dataclass
class ViCareButtonEntityDescription(
    ButtonEntityDescription, ViCareRequiredKeysMixinWithSet
):
    """Describes ViCare button entity."""


BUTTON_DESCRIPTIONS: tuple[ViCareButtonEntityDescription, ...] = (
    ViCareButtonEntityDescription(
        key=BUTTON_DHW_ACTIVATE_ONETIME_CHARGE,
        name="Activate one-time charge",
        icon="mdi:shower-head",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getOneTimeCharge(),
        value_setter=lambda api: api.activateOneTimeCharge(),
    ),
)


def _build_entity(
    name, vicare_api, device_config, description, has_multiple_devices: bool
):
    """Create a ViCare button entity."""
    _LOGGER.debug("Found device %s", name)
    try:
        description.value_getter(vicare_api)
        _LOGGER.debug("Found entity %s", name)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("Feature not supported %s", name)
        return None
    except AttributeError:
        _LOGGER.debug("Attribute Error %s", name)
        return None

    return ViCareButton(
        name,
        vicare_api,
        device_config,
        description,
        has_multiple_devices,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare button entities."""
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
        for description in BUTTON_DESCRIPTIONS:
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

    async_add_entities(entities)


class ViCareButton(ViCareEntity, ButtonEntity):
    """Representation of a ViCare button."""

    _attr_has_entity_name = True
    entity_description: ViCareButtonEntityDescription

    def __init__(
        self,
        name,
        api,
        device_config,
        description: ViCareButtonEntityDescription,
        has_multiple_devices: bool,
    ) -> None:
        """Initialize the button."""
        self.entity_description = description
        self._device_config = device_config
        self._api = api
        ViCareEntity.__init__(self, device_config, has_multiple_devices)

    def press(self) -> None:
        """Handle the button press."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self.entity_description.value_setter(self._api)
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)

    @property
    def unique_id(self) -> str:
        """Return unique ID for this device."""
        tmp_id = (
            f"{self._device_config.getConfig().serial}-{self.entity_description.key}"
        )
        if hasattr(self._api, "id"):
            return f"{tmp_id}-{self._api.id}"
        return tmp_id
