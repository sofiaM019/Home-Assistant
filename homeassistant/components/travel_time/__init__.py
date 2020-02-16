"""The travel_time integration."""
from datetime import timedelta
import logging
from typing import Dict, Optional, Union

import voluptuous as vol

from homeassistant.const import ATTR_ATTRIBUTION
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

from .const import (
    ATTR_DESTINATION,
    ATTR_DESTINATION_ADDRESS,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_DURATION_IN_TRAFFIC,
    ATTR_ORIGIN,
    ATTR_ORIGIN_ADDRESS,
    ATTR_ROUTE,
    ATTR_TRAVEL_MODE,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_DESTINATION_NAME,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
    CONF_ORIGIN_NAME,
    DOMAIN,
    UNIT_OF_MEASUREMENT,
)

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(minutes=5)

TRAVEL_TIME_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Inclusive(CONF_DESTINATION_LATITUDE, "destination_coordinates"): vol.Any(
            cv.latitude, cv.template
        ),
        vol.Inclusive(CONF_DESTINATION_LONGITUDE, "destination_coordinates"): vol.Any(
            cv.longitude, cv.template
        ),
        vol.Inclusive(CONF_ORIGIN_LATITUDE, "origin_coordinates"): vol.Any(
            cv.latitude, cv.template
        ),
        vol.Inclusive(CONF_ORIGIN_LONGITUDE, "origin_coordinates"): vol.Any(
            cv.longitude, cv.template
        ),
        vol.Exclusive(CONF_DESTINATION_LATITUDE, "destination"): vol.Any(
            cv.latitude, cv.template
        ),
        vol.Exclusive(CONF_DESTINATION_NAME, "destination"): vol.Any(
            cv.string, cv.template
        ),
        vol.Exclusive(CONF_ORIGIN_LATITUDE, "origin"): vol.Any(
            cv.latitude, cv.template
        ),
        vol.Exclusive(CONF_ORIGIN_NAME, "origin"): vol.Any(cv.string, cv.template),
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_DESTINATION_LATITUDE, CONF_DESTINATION_NAME),
    cv.has_at_least_one_key(CONF_ORIGIN_LATITUDE, CONF_ORIGIN_NAME),
    TRAVEL_TIME_SCHEMA,
)


async def async_setup(hass, config):
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class TravelTimeEntity(Entity):
    """Representation of a travel_time entity."""

    @property
    def attribution(self) -> str:
        """Get the attribution of the travel_time entity."""
        return None

    @property
    def destination(self) -> str:
        """Get the destination coordinates of the travel_time entity."""
        return None

    @property
    def destination_address(self) -> str:
        """Get the destination address of the travel_time entity."""
        return None

    @property
    def distance(self) -> str:
        """Get the distance of the travel_time entity."""
        return None

    @property
    def duration(self) -> str:
        """Get the duration without traffic of the travel_time entity."""
        return None

    @property
    def duration_in_traffic(self) -> str:
        """Get the duration with traffic of the travel_time entity."""
        return None

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return None

    @property
    def travel_mode(self) -> str:
        """Get the mode of travelling e.g car for this entity."""
        return None

    @property
    def name(self) -> str:
        """Get the name of the travel_time entity."""
        return None

    @property
    def origin(self) -> str:
        """Get the origin coordinates of the travel_time entity."""
        return None

    @property
    def origin_address(self) -> str:
        """Get the origin address of the travel_time entity."""
        return None

    @property
    def route(self) -> str:
        """Get the route of the travel_time entity."""
        return None

    @property
    def state(self) -> Optional[str]:
        """Return the state of the travel_time entity."""
        return self.duration

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return UNIT_OF_MEASUREMENT

    @property
    def state_attributes(self,) -> Optional[Dict[str, Union[None, float, str, bool]]]:
        """Return the state attributes."""
        res = {}
        if self.attribution is not None:
            res[ATTR_ATTRIBUTION] = self.attribution

        if self.destination is not None:
            res[ATTR_DESTINATION] = self.destination

        if self.destination_address is not None:
            res[ATTR_DESTINATION_ADDRESS] = self.destination_address

        if self.distance is not None:
            res[ATTR_DISTANCE] = self.distance

        if self.duration is not None:
            res[ATTR_DURATION] = self.duration

        if self.duration_in_traffic is not None:
            res[ATTR_DURATION_IN_TRAFFIC] = self.duration_in_traffic

        if self.travel_mode is not None:
            res[ATTR_TRAVEL_MODE] = self.travel_mode

        if self.origin is not None:
            res[ATTR_ORIGIN] = self.origin

        if self.origin_address is not None:
            res[ATTR_ORIGIN_ADDRESS] = self.origin_address

        if self.route is not None:
            res[ATTR_ROUTE] = self.route

        return res
