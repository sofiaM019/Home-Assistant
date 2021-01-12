"""The dhcp integration."""

import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

from scapy import DHCP, AsyncSniffer, Ether

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP

FILTER = "udp and (port 67 or 68)"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the dhcp component."""

    async def _initialize(_):
        dhcp_watcher = AsyncSniffer(filter=FILTER, prn=_handle_dhcp_packet)
        dhcp_watcher.start()
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, dhcp_watcher.stop)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _initialize)
    return True


def _extact_option(dhcp_options, key):
    """Extract and decode data from a packet option."""
    try:
        for i in dhcp_options:
            if i[0] != key:
                continue
            # decode to unicode string before returning
            return i[1].decode() if key == "hostname" else i[i]
    except Exception:  # pylint: disable=broad-except
        pass


def _handle_dhcp_packet(packet):
    """Process a dhcp packet."""
    if DHCP not in packet:
        return

    # DHCP request
    if packet[DHCP].options[0][1] == 3:
        options = packet[DHCP].options
        requested_addr = _extact_option(options, "requested_addr")
        hostname = _extact_option(options, "hostname")
        _LOGGER.warning(
            f"Host {hostname} ({packet[Ether].src}) requested {requested_addr}"
        )

    return
