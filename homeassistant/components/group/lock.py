"""Platform allowing several locks to be grouped into one lock."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.lock import (
    DOMAIN,
    PLATFORM_SCHEMA,
    LockEntity,
    LockEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    STATE_UNLOCKING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity

DEFAULT_NAME = "Lock Group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Lock Group platform."""
    async_add_entities(
        [
            LockGroup(
                hass,
                config.get(CONF_UNIQUE_ID),
                config[CONF_NAME],
                config[CONF_ENTITIES],
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Lock Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )
    async_add_entities(
        [
            LockGroup(
                hass,
                config_entry.entry_id,
                config_entry.title,
                entities,
                config_entry.options.get(CONF_DEVICE_ID, None),
            )
        ]
    )


@callback
def async_create_preview_lock(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> LockGroup:
    """Create a preview sensor."""
    return LockGroup(
        hass,
        None,
        name,
        validated_config[CONF_ENTITIES],
    )


class LockGroup(GroupEntity, LockEntity):
    """Representation of a lock group."""

    _attr_available = False
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        unique_id: str | None,
        name: str,
        entity_ids: list[str],
        device_id: str | None = None,
    ) -> None:
        """Initialize a lock group."""
        self._entity_ids = entity_ids
        self._attr_supported_features = LockEntityFeature.OPEN

        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}
        self._attr_unique_id = unique_id

        dev_reg = dr.async_get(hass)
        if (
            device_id is not None
            and (device := dev_reg.async_get(device_id)) is not None
        ):
            self._attr_device_info = DeviceInfo(
                connections=device.connections,
                identifiers=device.identifiers,
            )

    async def async_lock(self, **kwargs: Any) -> None:
        """Forward the lock command to all locks in the group."""
        data = {ATTR_ENTITY_ID: self._entity_ids}
        _LOGGER.debug("Forwarded lock command: %s", data)

        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_LOCK,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Forward the unlock command to all locks in the group."""
        data = {ATTR_ENTITY_ID: self._entity_ids}
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_UNLOCK,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_open(self, **kwargs: Any) -> None:
        """Forward the open command to all locks in the group."""
        data = {ATTR_ENTITY_ID: self._entity_ids}
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_OPEN,
            data,
            blocking=True,
            context=self._context,
        )

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the lock group state."""
        states = [
            state.state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]

        valid_state = any(
            state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        )

        if not valid_state:
            # Set as unknown if any member is unknown or unavailable
            self._attr_is_jammed = None
            self._attr_is_locking = None
            self._attr_is_opening = None
            self._attr_is_open = None
            self._attr_is_unlocking = None
            self._attr_is_locked = None
        else:
            # Set attributes based on member states and let the lock entity sort out the correct state
            self._attr_is_jammed = STATE_JAMMED in states
            self._attr_is_locking = STATE_LOCKING in states
            self._attr_is_opening = STATE_OPENING in states
            self._attr_is_open = STATE_OPEN in states
            self._attr_is_unlocking = STATE_UNLOCKING in states
            self._attr_is_locked = all(state == STATE_LOCKED for state in states)

        self._attr_available = any(state != STATE_UNAVAILABLE for state in states)
