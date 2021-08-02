"""Test UPnP/IGD setup process."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
)
from homeassistant.components.upnp.device import Device
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

from .mock_device import MockDevice

from tests.common import MockConfigEntry


class MockSsdpDescriptionManager(ssdp.DescriptionManager):
    """Mocked ssdp DescriptionManager."""

    async def fetch_description(
        self, xml_location: str | None
    ) -> None | dict[str, str]:
        """Fetch the location or get it from the cache."""
        if xml_location is None:
            return None
        return {}


class MockSsdpScanner(ssdp.Scanner):
    """Mocked ssdp Scanner."""

    @callback
    def async_stop(self, *_: Any) -> None:
        """Stop the scanner."""
        # Do nothing.

    async def async_start(self) -> None:
        """Start the scanner."""
        self.description_manager = MockSsdpDescriptionManager(self.hass)

    @callback
    def async_scan(self, *_: Any) -> None:
        """Scan for new entries."""
        # Do nothing.


async def test_async_setup_entry_default(hass: HomeAssistant):
    """Test async_setup_entry."""
    udn = "uuid:device_1"
    location = "http://192.168.1.1/desc.xml"
    mock_device = MockDevice(udn)
    discovery = {
        ssdp.ATTR_SSDP_LOCATION: location,
        ssdp.ATTR_SSDP_ST: mock_device.device_type,
        ssdp.ATTR_SSDP_USN: mock_device.usn,
        ssdp.ATTR_UPNP_UDN: mock_device.udn,
        "location": location,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: mock_device.udn,
            CONFIG_ENTRY_ST: mock_device.device_type,
        },
    )

    config = {
        # no upnp
    }
    async_create_device = AsyncMock(return_value=mock_device)
    with patch.object(Device, "async_create_device", async_create_device), patch(
        "homeassistant.components.ssdp.Scanner", MockSsdpScanner
    ):
        # initialisation of component, no device discovered
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        # cheat by filling SSDP cache
        scanner: ssdp.Scanner = hass.data[ssdp.DOMAIN]
        scanner.cache[
            (udn, "urn:schemas-upnp-org:device:InternetGatewayDevice:1")
        ] = discovery

        # loading of config_entry, device discovered
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id) is True

        # ensure device is stored/used
        async_create_device.assert_called_with(hass, discovery[ssdp.ATTR_SSDP_LOCATION])
