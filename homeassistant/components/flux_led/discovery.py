"""The Flux LED/MagicLight integration discovery."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, Final

from flux_led.aioscanner import AIOBulbScanner
from flux_led.const import (
    ATTR_ID,
    ATTR_IPADDR,
    ATTR_MODEL,
    ATTR_MODEL_DESCRIPTION,
    ATTR_MODEL_INFO,
    ATTR_MODEL_NUM,
    ATTR_REMOTE_ACCESS_ENABLED,
    ATTR_REMOTE_ACCESS_HOST,
    ATTR_REMOTE_ACCESS_PORT,
    ATTR_VERSION_NUM,
)
from flux_led.scanner import FluxLEDDiscovery

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.util.network import is_ip_address

from .const import (
    CONF_MINOR_VERSION,
    CONF_MODEL,
    CONF_MODEL_DESCRIPTION,
    CONF_MODEL_INFO,
    CONF_MODEL_NUM,
    CONF_REMOTE_ACCESS_ENABLED,
    CONF_REMOTE_ACCESS_HOST,
    CONF_REMOTE_ACCESS_PORT,
    DISCOVER_SCAN_TIMEOUT,
    DOMAIN,
    FLUX_LED_DISCOVERY,
)
from .util import format_as_flux_mac

_LOGGER = logging.getLogger(__name__)


CONF_TO_DISCOVERY: Final = {
    CONF_HOST: ATTR_IPADDR,
    CONF_REMOTE_ACCESS_ENABLED: ATTR_REMOTE_ACCESS_ENABLED,
    CONF_REMOTE_ACCESS_HOST: ATTR_REMOTE_ACCESS_HOST,
    CONF_REMOTE_ACCESS_PORT: ATTR_REMOTE_ACCESS_PORT,
    CONF_MINOR_VERSION: ATTR_VERSION_NUM,
    CONF_MODEL: ATTR_MODEL,
    CONF_MODEL_NUM: ATTR_MODEL_NUM,
    CONF_MODEL_INFO: ATTR_MODEL_INFO,
    CONF_MODEL_DESCRIPTION: ATTR_MODEL_DESCRIPTION,
}


@callback
def async_build_cached_discovery(entry: ConfigEntry) -> FluxLEDDiscovery:
    """When discovery is unavailable, load it from the config entry."""
    data = entry.data
    return FluxLEDDiscovery(
        ipaddr=data[CONF_HOST],
        model=data.get(CONF_MODEL),
        id=format_as_flux_mac(entry.unique_id),
        model_num=data.get(CONF_MODEL_NUM),
        version_num=data.get(CONF_MINOR_VERSION),
        firmware_date=None,
        model_info=data.get(CONF_MODEL_INFO),
        model_description=data.get(CONF_MODEL_DESCRIPTION),
        remote_access_enabled=data.get(CONF_REMOTE_ACCESS_ENABLED),
        remote_access_host=data.get(CONF_REMOTE_ACCESS_HOST),
        remote_access_port=data.get(CONF_REMOTE_ACCESS_PORT),
    )


@callback
def async_name_from_discovery(device: FluxLEDDiscovery) -> str:
    """Convert a flux_led discovery to a human readable name."""
    mac_address = device[ATTR_ID]
    if mac_address is None:
        return device[ATTR_IPADDR]
    short_mac = mac_address[-6:]
    if device[ATTR_MODEL_DESCRIPTION]:
        return f"{device[ATTR_MODEL_DESCRIPTION]} {short_mac}"
    return f"{device[ATTR_MODEL]} {short_mac}"


@callback
def async_populate_data_from_discovery(
    current_data: Mapping[str, Any],
    data_updates: dict[str, Any],
    device: FluxLEDDiscovery,
) -> None:
    """Copy discovery data into config entry data."""
    for conf_key, discovery_key in CONF_TO_DISCOVERY.items():
        if (
            device.get(discovery_key) is not None
            and conf_key not in data_updates
            and current_data.get(conf_key) != device[discovery_key]  # type: ignore[misc]
        ):
            data_updates[conf_key] = device[discovery_key]  # type: ignore[misc]


@callback
def async_update_entry_from_discovery(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    device: FluxLEDDiscovery,
    model_num: int | None,
) -> bool:
    """Update a config entry from a flux_led discovery."""
    data_updates: dict[str, Any] = {}
    mac_address = device[ATTR_ID]
    assert mac_address is not None
    updates: dict[str, Any] = {}
    if not entry.unique_id:
        updates["unique_id"] = dr.format_mac(mac_address)
    if model_num and entry.data.get(CONF_MODEL_NUM) != model_num:
        data_updates[CONF_MODEL_NUM] = model_num
    async_populate_data_from_discovery(entry.data, data_updates, device)
    if not entry.data.get(CONF_NAME) or is_ip_address(entry.data[CONF_NAME]):
        updates["title"] = data_updates[CONF_NAME] = async_name_from_discovery(device)
    if data_updates:
        updates["data"] = {**entry.data, **data_updates}
    if updates:
        return hass.config_entries.async_update_entry(entry, **updates)
    return False


@callback
def async_get_discovery(hass: HomeAssistant, host: str) -> FluxLEDDiscovery | None:
    """Check if a device was already discovered via a broadcast discovery."""
    discoveries: list[FluxLEDDiscovery] = hass.data[DOMAIN][FLUX_LED_DISCOVERY]
    for discovery in discoveries:
        if discovery[ATTR_IPADDR] == host:
            return discovery
    return None


@callback
def async_clear_discovery_cache(hass: HomeAssistant, host: str) -> None:
    """Clear the host from the discovery cache."""
    domain_data = hass.data[DOMAIN]
    discoveries: list[FluxLEDDiscovery] = domain_data[FLUX_LED_DISCOVERY]
    domain_data[FLUX_LED_DISCOVERY] = [
        discovery for discovery in discoveries if discovery[ATTR_IPADDR] != host
    ]


async def async_discover_devices(
    hass: HomeAssistant, timeout: int, address: str | None = None
) -> list[FluxLEDDiscovery]:
    """Discover flux led devices."""
    if address:
        targets = [address]
    else:
        targets = [
            str(address)
            for address in await network.async_get_ipv4_broadcast_addresses(hass)
        ]

    scanner = AIOBulbScanner()
    for idx, discovered in enumerate(
        await asyncio.gather(
            *[
                scanner.async_scan(timeout=timeout, address=address)
                for address in targets
            ],
            return_exceptions=True,
        )
    ):
        if isinstance(discovered, Exception):
            _LOGGER.debug("Scanning %s failed with error: %s", targets[idx], discovered)
            continue

    if not address:
        return scanner.getBulbInfo()

    return [
        device for device in scanner.getBulbInfo() if device[ATTR_IPADDR] == address
    ]


async def async_discover_device(
    hass: HomeAssistant, host: str
) -> FluxLEDDiscovery | None:
    """Direct discovery at a single ip instead of broadcast."""
    # If we are missing the unique_id we should be able to fetch it
    # from the device by doing a directed discovery at the host only
    for device in await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT, host):
        if device[ATTR_IPADDR] == host:
            return device
    return None


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: list[FluxLEDDiscovery],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_DISCOVERY},
                data={**device},
            )
        )
