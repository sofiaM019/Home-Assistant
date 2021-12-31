"""Test the Wevolor Control for Levolor Motorized Blinds config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.wevolor.const import (
    CONFIG_CHANNELS,
    CONFIG_HOST,
    CONFIG_TILT,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.wevolor.config_flow.Wevolor.get_status",
        return_value={"remote": "My Wevolor"},
    ), patch(
        "homeassistant.components.wevolor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONFIG_HOST: "1.1.1.1",
                CONFIG_TILT: True,
                CONFIG_CHANNELS: 3,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "My Wevolor"
    assert result2["data"] == {
        CONFIG_HOST: "1.1.1.1",
        CONFIG_TILT: True,
        CONFIG_CHANNELS: 3,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wevolor.config_flow.Wevolor.get_status",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONFIG_HOST: "1.1.1.1",
                CONFIG_TILT: True,
                CONFIG_CHANNELS: 3,
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}
