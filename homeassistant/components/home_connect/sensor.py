"""Provides a sensor for Home Connect."""
from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from .const import ATTR_VALUE, BSH_OPERATION_STATE, DOMAIN
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect sensor."""

    def get_entities():
        """Get a list of entities."""
        entities = []
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get(CONF_ENTITIES, {}).get("sensor", [])
            entities += [HomeConnectSensor(**d) for d in entity_dicts]
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectSensor(HomeConnectEntity, SensorEntity):
    """Sensor class for Home Connect."""

    def __init__(
        self,
        device,
        desc,
        key,
        unit,
        icon,
        device_class,
        translation_key: str | None,
        sign=1,
    ) -> None:
        """Initialize the entity."""
        super().__init__(device, desc)
        self._state: str | None = None
        self._key = key
        self._unit = unit
        self._icon = icon
        self._device_class = device_class
        self._sign = sign
        self._attr_translation_key = translation_key

    @property
    def native_value(self) -> StateType:
        """Return sensor value."""
        return self._state

    @property
    def available(self) -> bool:
        """Return true if the sensor is available."""
        return self._state is not None

    async def async_update(self) -> None:
        """Update the sensor's status."""
        status = self.device.appliance.status
        if self._key not in status:
            self._state = None
        elif self.device_class == SensorDeviceClass.TIMESTAMP:
            parsed_datetime: datetime | None = None
            if self._state is not None:
                parsed_datetime = dt_util.parse_datetime(self._state)

            if ATTR_VALUE not in status[self._key]:
                self._state = None
            elif (
                self._state is not None
                and self._sign == 1
                and parsed_datetime is not None
                and parsed_datetime < dt_util.utcnow()
            ):
                # if the date is supposed to be in the future but we're
                # already past it, set state to None.
                self._state = None
            else:
                seconds = self._sign * float(status[self._key][ATTR_VALUE])
                self._state = (
                    dt_util.utcnow() + timedelta(seconds=seconds)
                ).isoformat()
        else:
            self._state = status[self._key].get(ATTR_VALUE)
            if self._key == BSH_OPERATION_STATE:
                # Value comes back as an enum, we only really care about the
                # last part, so split it off
                # https://developer.home-connect.com/docs/status/operation_state
                if self._state is not None and isinstance(self._state, str):
                    self._state = self._state.split(".")[-1].lower()
        _LOGGER.debug("Updated, new state: %s", self._state)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return self._icon

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class."""
        return self._device_class
