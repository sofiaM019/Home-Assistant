"""The NextDNS component."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError, NextDns

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_CONNECTION,
    ATTR_DNSSEC,
    ATTR_ENCRYPTION,
    ATTR_IP_VERSIONS,
    ATTR_PROTOCOLS,
    ATTR_SETTINGS,
    ATTR_STATUS,
    CONF_PROFILE_ID,
    UPDATE_INTERVAL_ANALYTICS,
    UPDATE_INTERVAL_CONNECTION,
    UPDATE_INTERVAL_SETTINGS,
)
from .coordinator import (
    NextDnsConnectionUpdateCoordinator,
    NextDnsDnssecUpdateCoordinator,
    NextDnsEncryptionUpdateCoordinator,
    NextDnsIpVersionsUpdateCoordinator,
    NextDnsProtocolsUpdateCoordinator,
    NextDnsSettingsUpdateCoordinator,
    NextDnsStatusUpdateCoordinator,
    NextDnsUpdateCoordinator,
)

NextDnsConfigEntry = ConfigEntry["NextDnsData"]


@dataclass
class NextDnsData:
    """Data for the NextDNS integration."""

    connection: NextDnsUpdateCoordinator
    dnssec: NextDnsUpdateCoordinator
    encryption: NextDnsUpdateCoordinator
    ip_versions: NextDnsUpdateCoordinator
    protocols: NextDnsUpdateCoordinator
    settings: NextDnsUpdateCoordinator
    status: NextDnsUpdateCoordinator


PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]
COORDINATORS: list[tuple[str, type[NextDnsUpdateCoordinator], timedelta]] = [
    (ATTR_CONNECTION, NextDnsConnectionUpdateCoordinator, UPDATE_INTERVAL_CONNECTION),
    (ATTR_DNSSEC, NextDnsDnssecUpdateCoordinator, UPDATE_INTERVAL_ANALYTICS),
    (ATTR_ENCRYPTION, NextDnsEncryptionUpdateCoordinator, UPDATE_INTERVAL_ANALYTICS),
    (ATTR_IP_VERSIONS, NextDnsIpVersionsUpdateCoordinator, UPDATE_INTERVAL_ANALYTICS),
    (ATTR_PROTOCOLS, NextDnsProtocolsUpdateCoordinator, UPDATE_INTERVAL_ANALYTICS),
    (ATTR_SETTINGS, NextDnsSettingsUpdateCoordinator, UPDATE_INTERVAL_SETTINGS),
    (ATTR_STATUS, NextDnsStatusUpdateCoordinator, UPDATE_INTERVAL_ANALYTICS),
]


async def async_setup_entry(hass: HomeAssistant, entry: NextDnsConfigEntry) -> bool:
    """Set up NextDNS as config entry."""
    api_key = entry.data[CONF_API_KEY]
    profile_id = entry.data[CONF_PROFILE_ID]

    websession = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(10):
            nextdns = await NextDns.create(websession, api_key)
    except (ApiError, ClientConnectorError, TimeoutError) as err:
        raise ConfigEntryNotReady from err

    tasks = []
    coordinators = {}

    # Independent DataUpdateCoordinator is used for each API endpoint to avoid
    # unnecessary requests when entities using this endpoint are disabled.
    for coordinator_name, coordinator_class, update_interval in COORDINATORS:
        coordinator = coordinator_class(hass, nextdns, profile_id, update_interval)
        tasks.append(coordinator.async_config_entry_first_refresh())
        coordinators[coordinator_name] = coordinator

    await asyncio.gather(*tasks)

    entry.runtime_data = NextDnsData(**coordinators)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NextDnsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
