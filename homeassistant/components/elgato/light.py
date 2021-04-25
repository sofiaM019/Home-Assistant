"""Support for LED lights."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Callable

from elgato import Elgato, ElgatoError, Info, State

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_ON,
    ATTR_SOFTWARE_VERSION,
    DATA_ELGATO_CLIENT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up Elgato Key Light based on a config entry."""
    elgato: Elgato = hass.data[DOMAIN][entry.entry_id][DATA_ELGATO_CLIENT]
    info = await elgato.info()
    async_add_entities([ElgatoLight(elgato, info)], True)


class ElgatoLight(LightEntity):
    """Defines a Elgato Key Light."""

    def __init__(
        self,
        elgato: Elgato,
        info: Info,
    ):
        """Initialize Elgato Key Light."""
        self._info: Info = info
        self._state: State | None = None
        self.elgato = elgato

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        # Return the product name, if display name is not set
        return self._info.display_name or self._info.product_name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._state is not None

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return self._info.serial_number

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        assert self._state is not None
        return round((self._state.brightness * 255) / 100)

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        assert self._state is not None
        return self._state.temperature

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return 143

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return 344

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        assert self._state is not None
        return self._state.on

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.async_turn_on(on=False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        data: dict[str, bool | int] = {ATTR_ON: True}

        if ATTR_ON in kwargs:
            data[ATTR_ON] = kwargs[ATTR_ON]

        if ATTR_COLOR_TEMP in kwargs:
            data[ATTR_TEMPERATURE] = kwargs[ATTR_COLOR_TEMP]

        if ATTR_BRIGHTNESS in kwargs:
            data[ATTR_BRIGHTNESS] = round((kwargs[ATTR_BRIGHTNESS] / 255) * 100)

        try:
            await self.elgato.light(**data)
        except ElgatoError:
            _LOGGER.error("An error occurred while updating the Elgato Key Light")
            self._state = None

    async def async_update(self) -> None:
        """Update Elgato entity."""
        restoring = self._state is None
        try:
            self._state: State = await self.elgato.state()
            if restoring:
                _LOGGER.info("Connection restored")
        except ElgatoError as err:
            meth = _LOGGER.error if self._state else _LOGGER.debug
            meth("An error occurred while updating the Elgato Key Light: %s", err)
            self._state = None

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this Elgato Key Light."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._info.serial_number)},
            ATTR_NAME: self._info.product_name,
            ATTR_MANUFACTURER: "Elgato",
            ATTR_MODEL: self._info.product_name,
            ATTR_SOFTWARE_VERSION: f"{self._info.firmware_version} ({self._info.firmware_build_number})",
        }
