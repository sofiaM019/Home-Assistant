"""The Roborock component."""
from __future__ import annotations

from datetime import timedelta
import logging

from roborock.api import RoborockClient, RoborockMqttClient
from roborock.containers import HomeDataProduct, UserData
from roborock.typing import RoborockDeviceInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_BASE_URL, CONF_USER_DATA, DOMAIN, PLATFORMS
from .coordinator import RoborockDataUpdateCoordinator

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up roborock from a config entry."""
    _LOGGER.debug("Integration async setup entry: %s", entry.as_dict())

    user_data = UserData(entry.data[CONF_USER_DATA])
    api_client = RoborockClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_BASE_URL]
    )
    _LOGGER.debug("Getting home data")
    home_data = await api_client.get_home_data(user_data)
    _LOGGER.debug("Got home data %s", home_data)

    device_map: dict[str, RoborockDeviceInfo] = {}
    devices = home_data.devices + home_data.received_devices
    for device in devices:
        product: HomeDataProduct = next(
            (
                HomeDataProduct(product)
                for product in home_data.products
                if product.id == device.product_id
            ),
            {},
        )
        device_map[device.duid] = RoborockDeviceInfo(device, product)

    client = RoborockMqttClient(user_data, device_map)
    coordinator = RoborockDataUpdateCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await hass.data[DOMAIN][entry.entry_id].release()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
