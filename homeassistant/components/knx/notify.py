"""Support for KNX/IP notifications."""

from __future__ import annotations

from typing import Any

from xknx import XKNX
from xknx.devices import Notification as XknxNotification

from homeassistant import config_entries
from homeassistant.components.notify import NotifyEntity
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import DATA_KNX_CONFIG, DOMAIN, KNX_ADDRESS
from .knx_entity import KnxEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up notify(s) for KNX platform."""
    xknx: XKNX = hass.data[DOMAIN].xknx
    config: list[ConfigType] = hass.data[DATA_KNX_CONFIG][Platform.NOTIFY]

    async_add_entities(KNXNotify(xknx, entity_config) for entity_config in config)


def _create_notification_instance(xknx: XKNX, config: ConfigType) -> XknxNotification:
    """Return a KNX Notification to be used within XKNX."""
    return XknxNotification(
        xknx,
        name=config[CONF_NAME],
        group_address=config[KNX_ADDRESS],
        value_type=config[CONF_TYPE],
    )


class KNXNotify(NotifyEntity, KnxEntity):
    """Representation of a KNX notification entity."""

    _device: XknxNotification

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize a KNX notification."""
        super().__init__(_create_notification_instance(xknx, config))
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = str(self._device.remote_value.group_address)

    async def async_send_message(self, message: str) -> None:
        """Send a notification to knx bus."""
        await self._device.set(message)
