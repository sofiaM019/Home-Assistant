"""Test UPnP/IGD setup process."""

from ipaddress import IPv4Address

from homeassistant.components import upnp
from homeassistant.components.upnp.const import (
    DISCOVERY_LOCATION,
    DISCOVERY_ST,
    DISCOVERY_UDN,
)
from homeassistant.components.upnp.device import Device
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry, mock_coro
from .mock_device import MockDevice


async def test_async_setup_entry_default(hass):
    """Test async_setup_entry."""
    udn = "uuid:device_1"
    mock_device = MockDevice(udn)
    entry = MockConfigEntry(domain=upnp.DOMAIN, data={"udn": udn, "st": mock_device.device_type})

    config = {
        # no upnp
    }
    with patch.object(Device, "async_create_device") as create_device, patch.object(
        Device, "async_discover"
    ) as async_discover:
        async_discover.return_value = mock_coro(return_value=[])

        await async_setup_component(hass, "upnp", config)
        await hass.async_block_till_done()

        # mock homeassistant.components.upnp.device.Device
        discovery_infos = [
            {
                DISCOVERY_UDN: mock_device.udn,
                DISCOVERY_ST: mock_device.device_type,
                DISCOVERY_LOCATION: "http://192.168.1.1/desc.xml",
            }
        ]
        create_device.return_value = mock_device
        async_discover.return_value = discovery_infos

        assert await upnp.async_setup_entry(hass, entry) is True

        # ensure device is stored/used
        assert hass.data[upnp.DOMAIN]["devices"][udn] == mock_device

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    # ensure no port-mappings created or removed
    assert not mock_device.added_port_mappings
    assert not mock_device.removed_port_mappings


async def test_async_setup_entry_port_mapping(hass):
    """Test async_setup_entry."""
    # pylint: disable=invalid-name
    udn = "uuid:device_1"
    mock_device = MockDevice(udn)
    entry = MockConfigEntry(domain=upnp.DOMAIN, data={"udn": udn, "st": mock_device.device_type})

    config = {
        "http": {},
        "upnp": {
            "local_ip": "192.168.1.10",
            "port_mapping": True,
            "ports": {"hass": "hass"},
        },
    }
    with patch.object(Device, "async_create_device") as create_device, patch.object(
        Device, "async_discover"
    ) as async_discover:
        async_discover.return_value = mock_coro(return_value=[])

        await async_setup_component(hass, "http", config)
        await async_setup_component(hass, "upnp", config)
        await hass.async_block_till_done()

        discovery_infos = [
            {
                DISCOVERY_UDN: mock_device.udn,
                DISCOVERY_ST: mock_device.device_type,
                DISCOVERY_LOCATION: "http://192.168.1.1/desc.xml",
            }
        ]
        create_device.return_value = mock_device
        async_discover.return_value = discovery_infos

        assert await upnp.async_setup_entry(hass, entry) is True

        # ensure device is stored/used
        assert hass.data[upnp.DOMAIN]["devices"][udn] == mock_device

        # ensure add-port-mapping-methods called
        assert mock_device.added_port_mappings == [
            [8123, IPv4Address("192.168.1.10"), 8123]
        ]

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    # ensure delete-port-mapping-methods called
    assert mock_device.removed_port_mappings == [8123]
