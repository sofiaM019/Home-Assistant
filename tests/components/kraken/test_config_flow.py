"""Tests for the kraken config_flow."""
from homeassistant.components.kraken.const import CONF_TRACKED_ASSET_PAIRS, DOMAIN
from homeassistant.const import CONF_SCAN_INTERVAL

from .const import TICKER_INFORMATION_RESPONSE, TRADEABLE_ASSET_PAIR_RESPONSE

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_config_flow(hass):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"

    await hass.async_block_till_done()
    state = hass.states.get("sensor.xbt_usd_last_trade_closed")
    assert state


async def test_form_already_configured(hass):
    """Test is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"

    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_options(hass):
    """Test options for Kraken."""
    with patch(
        "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
        return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
    ), patch(
        "pykrakenapi.KrakenAPI.get_ticker_information",
        return_value=TICKER_INFORMATION_RESPONSE,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            options={
                CONF_SCAN_INTERVAL: 60,
                CONF_TRACKED_ASSET_PAIRS: [
                    "ADA/XBT",
                    "ADA/ETH",
                    "XBT/EUR",
                    "XBT/GBP",
                    "XBT/USD",
                    "XBT/JPY",
                ],
            },
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.xbt_usd_last_trade_closed")

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SCAN_INTERVAL: 10,
                CONF_TRACKED_ASSET_PAIRS: ["ADA/ETH"],
            },
        )
        assert result["type"] == "create_entry"
        await hass.async_block_till_done()

        ada_eth_sensor = hass.states.get("sensor.ada_eth_last_trade_closed")
        assert ada_eth_sensor.state == "0.0003478"

        assert hass.states.get("sensor.xbt_usd_last_trade_closed") is None
