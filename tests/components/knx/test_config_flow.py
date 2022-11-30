"""Test the KNX config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from xknx.exceptions.exception import InvalidSecureConfiguration
from xknx.io import DEFAULT_MCAST_GRP, DEFAULT_MCAST_PORT
from xknx.io.gateway_scanner import GatewayDescriptor

from homeassistant import config_entries
from homeassistant.components.knx.config_flow import (
    CONF_KNX_GATEWAY,
    CONF_KNX_TUNNELING_TYPE,
    DEFAULT_ENTRY_DATA,
    OPTION_MANUAL_TUNNEL,
)
from homeassistant.components.knx.const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_DEFAULT_STATE_UPDATER,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_KNXKEY_FILENAME,
    CONF_KNX_KNXKEY_PASSWORD,
    CONF_KNX_LOCAL_IP,
    CONF_KNX_MCAST_GRP,
    CONF_KNX_MCAST_PORT,
    CONF_KNX_RATE_LIMIT,
    CONF_KNX_ROUTE_BACK,
    CONF_KNX_ROUTING,
    CONF_KNX_ROUTING_BACKBONE_KEY,
    CONF_KNX_ROUTING_SECURE,
    CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE,
    CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
    CONF_KNX_SECURE_USER_ID,
    CONF_KNX_SECURE_USER_PASSWORD,
    CONF_KNX_STATE_UPDATER,
    CONF_KNX_TUNNELING,
    CONF_KNX_TUNNELING_TCP,
    CONF_KNX_TUNNELING_TCP_SECURE,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from tests.common import MockConfigEntry


def _gateway_descriptor(
    ip: str,
    port: int,
    supports_tunnelling_tcp: bool = False,
    requires_secure: bool = False,
) -> GatewayDescriptor:
    """Get mock gw descriptor."""
    descriptor = GatewayDescriptor(
        name="Test",
        ip_addr=ip,
        port=port,
        local_interface="eth0",
        local_ip="127.0.0.1",
        supports_routing=True,
        supports_tunnelling=True,
        supports_tunnelling_tcp=supports_tunnelling_tcp,
    )
    descriptor.tunnelling_requires_secure = requires_secure
    descriptor.routing_requires_secure = requires_secure
    return descriptor


class GatewayScannerMock:
    """Mock GatewayScanner."""

    def __init__(self, gateways=None):
        """Initialize GatewayScannerMock."""
        # Key is a HPAI instance in xknx, but not used in HA anyway.
        self.found_gateways = (
            {f"{gateway.ip_addr}:{gateway.port}": gateway for gateway in gateways}
            if gateways
            else {}
        )

    async def async_scan(self):
        """Mock async generator."""
        for gateway in self.found_gateways:
            yield gateway


async def test_user_single_instance(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_routing_setup(gateway_scanner_mock, hass: HomeAssistant) -> None:
    """Test routing setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "routing"
    assert result2["errors"] == {"base": "no_router_discovered"}

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
            },
        )
        await hass.async_block_till_done()
        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["title"] == "Routing as 1.1.110"
        assert result3["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_MCAST_PORT: 3675,
            CONF_KNX_LOCAL_IP: None,
            CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
        }

        assert len(mock_setup_entry.mock_calls) == 1


@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_routing_setup_advanced(
    gateway_scanner_mock, hass: HomeAssistant
) -> None:
    """Test routing setup with advanced options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_USER,
            "show_advanced_options": True,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "routing"
    assert result2["errors"] == {"base": "no_router_discovered"}

    # invalid user input
    result_invalid_input = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_MCAST_GRP: "10.1.2.3",  # no valid multicast group
            CONF_KNX_MCAST_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "not_a_valid_address",
            CONF_KNX_LOCAL_IP: "no_local_ip",
        },
    )
    await hass.async_block_till_done()
    assert result_invalid_input["type"] == FlowResultType.FORM
    assert result_invalid_input["step_id"] == "routing"
    assert result_invalid_input["errors"] == {
        CONF_KNX_MCAST_GRP: "invalid_ip_address",
        CONF_KNX_INDIVIDUAL_ADDRESS: "invalid_individual_address",
        CONF_KNX_LOCAL_IP: "invalid_ip_address",
        "base": "no_router_discovered",
    }

    # valid user input
    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
                CONF_KNX_LOCAL_IP: "192.168.1.112",
            },
        )
        await hass.async_block_till_done()
        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["title"] == "Routing as 1.1.110"
        assert result3["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_MCAST_PORT: 3675,
            CONF_KNX_LOCAL_IP: "192.168.1.112",
            CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
        }

        assert len(mock_setup_entry.mock_calls) == 1


@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_routing_secure_manual_setup(
    gateway_scanner_mock, hass: HomeAssistant
) -> None:
    """Test routing secure setup with manual key config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "routing"
    assert result2["errors"] == {"base": "no_router_discovered"}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_MCAST_PORT: 3671,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.123",
            CONF_KNX_ROUTING_SECURE: True,
        },
    )
    assert result3["type"] == FlowResultType.MENU
    assert result3["step_id"] == "secure_key_source"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {"next_step_id": "secure_routing_manual"},
    )
    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == "secure_routing_manual"
    assert not result4["errors"]

    result_invalid_key1 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        {
            CONF_KNX_ROUTING_BACKBONE_KEY: "xxaacc44bbaacc44bbaacc44bbaaccyy",  # invalid hex string
            CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: 2000,
        },
    )
    assert result_invalid_key1["type"] == FlowResultType.FORM
    assert result_invalid_key1["step_id"] == "secure_routing_manual"
    assert result_invalid_key1["errors"] == {"backbone_key": "invalid_backbone_key"}

    result_invalid_key2 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        {
            CONF_KNX_ROUTING_BACKBONE_KEY: "bbaacc44bbaacc44",  # invalid length
            CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: 2000,
        },
    )
    assert result_invalid_key2["type"] == FlowResultType.FORM
    assert result_invalid_key2["step_id"] == "secure_routing_manual"
    assert result_invalid_key2["errors"] == {"backbone_key": "invalid_backbone_key"}

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        secure_routing_manual = await hass.config_entries.flow.async_configure(
            result_invalid_key2["flow_id"],
            {
                CONF_KNX_ROUTING_BACKBONE_KEY: "bbaacc44bbaacc44bbaacc44bbaacc44",
                CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: 2000,
            },
        )
        await hass.async_block_till_done()
        assert secure_routing_manual["type"] == FlowResultType.CREATE_ENTRY
        assert secure_routing_manual["title"] == "Secure Routing as 0.0.123"
        assert secure_routing_manual["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING_SECURE,
            CONF_KNX_ROUTING_BACKBONE_KEY: "bbaacc44bbaacc44bbaacc44bbaacc44",
            CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: 2000,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.123",
        }
        assert len(mock_setup_entry.mock_calls) == 1


@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_routing_secure_keyfile(
    gateway_scanner_mock, hass: HomeAssistant
) -> None:
    """Test routing secure setup with keyfile."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "routing"
    assert result2["errors"] == {"base": "no_router_discovered"}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_MCAST_PORT: 3671,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.123",
            CONF_KNX_ROUTING_SECURE: True,
        },
    )
    assert result3["type"] == FlowResultType.MENU
    assert result3["step_id"] == "secure_key_source"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == "secure_knxkeys"
    assert not result4["errors"]

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.knx.config_flow.load_keyring", return_value=True
    ):
        routing_secure_knxkeys = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            {
                CONF_KNX_KNXKEY_FILENAME: "testcase.knxkeys",
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()
        assert routing_secure_knxkeys["type"] == FlowResultType.CREATE_ENTRY
        assert routing_secure_knxkeys["title"] == "Secure Routing as 0.0.123"
        assert routing_secure_knxkeys["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING_SECURE,
            CONF_KNX_KNXKEY_FILENAME: "knx/testcase.knxkeys",
            CONF_KNX_KNXKEY_PASSWORD: "password",
            CONF_KNX_ROUTING_BACKBONE_KEY: None,
            CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: None,
            CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
            CONF_KNX_SECURE_USER_ID: None,
            CONF_KNX_SECURE_USER_PASSWORD: None,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.123",
        }
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "user_input,config_entry_data",
    [
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_ROUTE_BACK: False,
            },
            {
                **DEFAULT_ENTRY_DATA,
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
                CONF_KNX_ROUTE_BACK: False,
                CONF_KNX_LOCAL_IP: None,
            },
        ),
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_ROUTE_BACK: False,
            },
            {
                **DEFAULT_ENTRY_DATA,
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
                CONF_KNX_ROUTE_BACK: False,
                CONF_KNX_LOCAL_IP: None,
            },
        ),
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_ROUTE_BACK: True,
            },
            {
                **DEFAULT_ENTRY_DATA,
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
                CONF_KNX_ROUTE_BACK: True,
                CONF_KNX_LOCAL_IP: None,
            },
        ),
    ],
)
@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_tunneling_setup_manual(
    gateway_scanner_mock, hass: HomeAssistant, user_input, config_entry_data
) -> None:
    """Test tunneling if no gateway was found found (or `manual` option was chosen)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "manual_tunnel"
    assert result2["errors"] == {"base": "no_tunnel_discovered"}

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input,
        )
        await hass.async_block_till_done()
        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["title"] == "Tunneling @ 192.168.0.1"
        assert result3["data"] == config_entry_data

        assert len(mock_setup_entry.mock_calls) == 1


@patch(
    "homeassistant.components.knx.config_flow.GatewayScanner",
    return_value=GatewayScannerMock(),
)
async def test_tunneling_setup_for_local_ip(
    gateway_scanner_mock, hass: HomeAssistant
) -> None:
    """Test tunneling if only one gateway is found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_USER,
            "show_advanced_options": True,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "manual_tunnel"
    assert result2["errors"] == {"base": "no_tunnel_discovered"}

    # invalid host ip address
    result_invalid_host = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING,
            CONF_HOST: DEFAULT_MCAST_GRP,  # multicast addresses are invalid
            CONF_PORT: 3675,
            CONF_KNX_LOCAL_IP: "192.168.1.112",
        },
    )
    await hass.async_block_till_done()
    assert result_invalid_host["type"] == FlowResultType.FORM
    assert result_invalid_host["step_id"] == "manual_tunnel"
    assert result_invalid_host["errors"] == {
        CONF_HOST: "invalid_ip_address",
        "base": "no_tunnel_discovered",
    }
    # invalid local ip address
    result_invalid_local = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING,
            CONF_HOST: "192.168.0.2",
            CONF_PORT: 3675,
            CONF_KNX_LOCAL_IP: "asdf",
        },
    )
    await hass.async_block_till_done()
    assert result_invalid_local["type"] == FlowResultType.FORM
    assert result_invalid_local["step_id"] == "manual_tunnel"
    assert result_invalid_local["errors"] == {
        CONF_KNX_LOCAL_IP: "invalid_ip_address",
        "base": "no_tunnel_discovered",
    }

    # valid user input
    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.2",
                CONF_PORT: 3675,
                CONF_KNX_LOCAL_IP: "192.168.1.112",
            },
        )
        await hass.async_block_till_done()
        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["title"] == "Tunneling @ 192.168.0.2"
        assert result3["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            CONF_HOST: "192.168.0.2",
            CONF_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
            CONF_KNX_ROUTE_BACK: False,
            CONF_KNX_LOCAL_IP: "192.168.1.112",
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_tunneling_setup_for_multiple_found_gateways(hass: HomeAssistant) -> None:
    """Test tunneling if multiple gateways are found."""
    gateway = _gateway_descriptor("192.168.0.1", 3675)
    gateway2 = _gateway_descriptor("192.168.1.100", 3675)
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway, gateway2])
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert not result["errors"]

    tunnel_flow = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    await hass.async_block_till_done()
    assert tunnel_flow["type"] == FlowResultType.FORM
    assert tunnel_flow["step_id"] == "tunnel"
    assert not tunnel_flow["errors"]

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            tunnel_flow["flow_id"],
            {CONF_KNX_GATEWAY: str(gateway)},
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
            CONF_KNX_ROUTE_BACK: False,
            CONF_KNX_LOCAL_IP: None,
        }

        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "gateway",
    [
        _gateway_descriptor("192.168.0.1", 3675),
        _gateway_descriptor("192.168.0.1", 3675, supports_tunnelling_tcp=True),
        _gateway_descriptor(
            "192.168.0.1", 3675, supports_tunnelling_tcp=True, requires_secure=True
        ),
    ],
)
async def test_manual_tunnel_step_with_found_gateway(
    hass: HomeAssistant, gateway
) -> None:
    """Test manual tunnel if gateway was found and tunneling is selected."""
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway])
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert not result["errors"]

    tunnel_flow = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    await hass.async_block_till_done()
    assert tunnel_flow["type"] == FlowResultType.FORM
    assert tunnel_flow["step_id"] == "tunnel"
    assert not tunnel_flow["errors"]

    manual_tunnel_flow = await hass.config_entries.flow.async_configure(
        tunnel_flow["flow_id"],
        {
            CONF_KNX_GATEWAY: OPTION_MANUAL_TUNNEL,
        },
    )
    await hass.async_block_till_done()
    assert manual_tunnel_flow["type"] == FlowResultType.FORM
    assert manual_tunnel_flow["step_id"] == "manual_tunnel"
    assert not manual_tunnel_flow["errors"]


async def test_form_with_automatic_connection_handling(hass: HomeAssistant) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock(
            [_gateway_descriptor("192.168.0.1", 3675)]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert not result["errors"]

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == CONF_KNX_AUTOMATIC.capitalize()
    assert result2["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def _get_menu_step(hass: HomeAssistant) -> FlowResult:
    """Return flow in secure_tunnelling menu step."""
    gateway = _gateway_descriptor(
        "192.168.0.1",
        3675,
        supports_tunnelling_tcp=True,
        requires_secure=True,
    )
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway])
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "tunnel"
    assert not result2["errors"]

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_KNX_GATEWAY: str(gateway)},
    )
    await hass.async_block_till_done()
    assert result3["type"] == FlowResultType.MENU
    assert result3["step_id"] == "secure_key_source"
    return result3


async def test_get_secure_menu_step_manual_tunnelling(
    hass: HomeAssistant,
):
    """Test flow reaches secure_tunnellinn menu step from manual tunnelling configuration."""
    gateway = _gateway_descriptor(
        "192.168.0.1",
        3675,
        supports_tunnelling_tcp=True,
        requires_secure=True,
    )
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway])
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "tunnel"
    assert not result2["errors"]

    manual_tunnel_flow = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_KNX_GATEWAY: OPTION_MANUAL_TUNNEL,
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        manual_tunnel_flow["flow_id"],
        {
            CONF_KNX_TUNNELING_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 3675,
        },
    )
    await hass.async_block_till_done()
    assert result3["type"] == FlowResultType.MENU
    assert result3["step_id"] == "secure_key_source"


async def test_configure_secure_tunnel_manual(hass: HomeAssistant):
    """Test configure tunnelling secure keys manually."""
    menu_step = await _get_menu_step(hass)

    result = await hass.config_entries.flow.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "secure_tunnel_manual"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "secure_tunnel_manual"
    assert not result["errors"]

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        secure_tunnel_manual = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KNX_SECURE_USER_ID: 2,
                CONF_KNX_SECURE_USER_PASSWORD: "password",
                CONF_KNX_SECURE_DEVICE_AUTHENTICATION: "device_auth",
            },
        )
        await hass.async_block_till_done()
        assert secure_tunnel_manual["type"] == FlowResultType.CREATE_ENTRY
        assert secure_tunnel_manual["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
            CONF_KNX_SECURE_USER_ID: 2,
            CONF_KNX_SECURE_USER_PASSWORD: "password",
            CONF_KNX_SECURE_DEVICE_AUTHENTICATION: "device_auth",
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
            CONF_KNX_ROUTE_BACK: False,
            CONF_KNX_LOCAL_IP: None,
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_configure_secure_knxkeys(hass: HomeAssistant):
    """Test configure secure knxkeys."""
    menu_step = await _get_menu_step(hass)

    result = await hass.config_entries.flow.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "secure_knxkeys"
    assert not result["errors"]

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.knx.config_flow.load_keyring", return_value=True
    ):
        secure_knxkeys = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KNX_KNXKEY_FILENAME: "testcase.knxkeys",
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()
        assert secure_knxkeys["type"] == FlowResultType.CREATE_ENTRY
        assert secure_knxkeys["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
            CONF_KNX_KNXKEY_FILENAME: "knx/testcase.knxkeys",
            CONF_KNX_KNXKEY_PASSWORD: "password",
            CONF_KNX_ROUTING_BACKBONE_KEY: None,
            CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: None,
            CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
            CONF_KNX_SECURE_USER_ID: None,
            CONF_KNX_SECURE_USER_PASSWORD: None,
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
            CONF_KNX_ROUTE_BACK: False,
            CONF_KNX_LOCAL_IP: None,
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_configure_secure_knxkeys_file_not_found(hass: HomeAssistant):
    """Test configure secure knxkeys but file was not found."""
    menu_step = await _get_menu_step(hass)

    result = await hass.config_entries.flow.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "secure_knxkeys"
    assert not result["errors"]

    with patch(
        "homeassistant.components.knx.config_flow.load_keyring",
        side_effect=FileNotFoundError(),
    ):
        secure_knxkeys = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KNX_KNXKEY_FILENAME: "testcase.knxkeys",
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()
        assert secure_knxkeys["type"] == FlowResultType.FORM
        assert secure_knxkeys["errors"]
        assert secure_knxkeys["errors"][CONF_KNX_KNXKEY_FILENAME] == "file_not_found"


async def test_configure_secure_knxkeys_invalid_signature(hass: HomeAssistant):
    """Test configure secure knxkeys but file was not found."""
    menu_step = await _get_menu_step(hass)

    result = await hass.config_entries.flow.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "secure_knxkeys"
    assert not result["errors"]

    with patch(
        "homeassistant.components.knx.config_flow.load_keyring",
        side_effect=InvalidSecureConfiguration(),
    ):
        secure_knxkeys = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KNX_KNXKEY_FILENAME: "testcase.knxkeys",
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()
        assert secure_knxkeys["type"] == FlowResultType.FORM
        assert secure_knxkeys["errors"]
        assert secure_knxkeys["errors"][CONF_KNX_KNXKEY_PASSWORD] == "invalid_signature"


@patch("homeassistant.components.knx.async_setup_entry", AsyncMock(return_value=True))
async def test_options_flow_connection_type(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow changing interface."""
    mock_config_entry.add_to_hass(hass)
    gateway = _gateway_descriptor("192.168.0.1", 3675)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    menu_step = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway])
        result = await hass.config_entries.options.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "connection_type"},
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "connection_type"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            },
        )
        assert result2.get("type") == FlowResultType.FORM
        assert result2.get("step_id") == "tunnel"

        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={
                CONF_KNX_GATEWAY: str(gateway),
            },
        )
        await hass.async_block_till_done()
        assert result3.get("type") == FlowResultType.CREATE_ENTRY
        assert not result3.get("data")
        assert mock_config_entry.data == {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 3675,
            CONF_KNX_LOCAL_IP: None,
            CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_RATE_LIMIT: 0,
            CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
            CONF_KNX_ROUTE_BACK: False,
        }


@patch("homeassistant.components.knx.async_setup_entry", AsyncMock(return_value=True))
async def test_options_flow_secure_manual_to_keyfile(hass: HomeAssistant) -> None:
    """Test options flow changing secure credential source."""
    mock_config_entry = MockConfigEntry(
        title="KNX",
        domain="knx",
        data={
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
            CONF_KNX_SECURE_USER_ID: 2,
            CONF_KNX_SECURE_USER_PASSWORD: "password",
            CONF_KNX_SECURE_DEVICE_AUTHENTICATION: "device_auth",
            CONF_KNX_KNXKEY_FILENAME: "knx/testcase.knxkeys",
            CONF_KNX_KNXKEY_PASSWORD: "invalid_password",
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
            CONF_KNX_ROUTE_BACK: False,
            CONF_KNX_LOCAL_IP: None,
        },
    )
    gateway = _gateway_descriptor(
        "192.168.0.1",
        3675,
        supports_tunnelling_tcp=True,
        requires_secure=True,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    menu_step = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    with patch(
        "homeassistant.components.knx.config_flow.GatewayScanner"
    ) as gateway_scanner_mock:
        gateway_scanner_mock.return_value = GatewayScannerMock([gateway])
        result = await hass.config_entries.options.async_configure(
            menu_step["flow_id"],
            {"next_step_id": "connection_type"},
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "connection_type"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            },
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "tunnel"
        assert not result2["errors"]

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        {CONF_KNX_GATEWAY: str(gateway)},
    )
    assert result3["type"] == FlowResultType.MENU
    assert result3["step_id"] == "secure_key_source"

    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        {"next_step_id": "secure_knxkeys"},
    )
    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == "secure_knxkeys"
    assert not result4["errors"]

    with patch(
        "homeassistant.components.knx.config_flow.load_keyring", return_value=True
    ):
        secure_knxkeys = await hass.config_entries.options.async_configure(
            result4["flow_id"],
            {
                CONF_KNX_KNXKEY_FILENAME: "testcase.knxkeys",
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()
    assert secure_knxkeys["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.data == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
        CONF_KNX_KNXKEY_FILENAME: "knx/testcase.knxkeys",
        CONF_KNX_KNXKEY_PASSWORD: "password",
        CONF_KNX_SECURE_DEVICE_AUTHENTICATION: None,
        CONF_KNX_SECURE_USER_ID: None,
        CONF_KNX_SECURE_USER_PASSWORD: None,
        CONF_KNX_ROUTING_BACKBONE_KEY: None,
        CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: None,
        CONF_HOST: "192.168.0.1",
        CONF_PORT: 3675,
        CONF_KNX_INDIVIDUAL_ADDRESS: "0.0.240",
        CONF_KNX_ROUTE_BACK: False,
        CONF_KNX_LOCAL_IP: None,
    }


@patch("homeassistant.components.knx.async_setup_entry", AsyncMock(return_value=True))
async def test_options_communication_settings(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow changing communication settings."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    menu_step = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        menu_step["flow_id"],
        {"next_step_id": "communication_settings"},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "communication_settings"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_KNX_STATE_UPDATER: False,
            CONF_KNX_RATE_LIMIT: 40,
        },
    )
    await hass.async_block_till_done()
    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert not result2.get("data")
    assert mock_config_entry.data == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
        CONF_KNX_STATE_UPDATER: False,
        CONF_KNX_RATE_LIMIT: 40,
    }
