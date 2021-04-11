"""Tests for the KNX integration."""

from unittest.mock import DEFAULT, patch

from homeassistant.components.knx.const import DOMAIN as KNX_DOMAIN
from homeassistant.setup import async_setup_component


async def setup_knx_integration(hass, knx_ip_interface, config=None):
    """Create the KNX gateway."""
    if config is None:
        config = {}

    # To get the XKNX object from the constructor call
    def side_effect(*args, **kwargs):
        knx_ip_interface.xknx = args[0]
        return DEFAULT

    with patch(
        "xknx.xknx.KNXIPInterface",
        return_value=knx_ip_interface,
        side_effect=side_effect,
    ):
        await async_setup_component(hass, KNX_DOMAIN, {KNX_DOMAIN: config})
        await hass.async_block_till_done()


async def async_wait_for_queue(knx_ip_interface_mock):
    """Wait for emptying the sending queue.

    Only then we'll find the telegrams in the ip interface.
    """
    await knx_ip_interface_mock.xknx.telegram_queue.outgoing_queue.join()
