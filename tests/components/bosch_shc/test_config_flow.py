"""Test the Bosch SHC config flow."""
from boschshcpy.information import SHCInformation

from homeassistant import config_entries, setup
from homeassistant.components.bosch_shc.config_flow import InvalidAuth
from homeassistant.components.bosch_shc.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "boschshcpy.session.SHCSession.acquire_information",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.information.SHCInformation.getMacAddress",
        return_value="ab:cd:ef:01:23:45",
    ), patch(
        "homeassistant.components.bosch_shc.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.bosch_shc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "ssl_certificate": "test-cert.pem",
                "ssl_key": "test-key.pem",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Bosch SHC"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "ssl_certificate": "test-cert.pem",
        "ssl_key": "test-key.pem",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "ssl_certificate": "test-cert.pem",
                "ssl_key": "test-key.pem",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_invalid_auth_from_shc(hass):
    """Test we handle invalid auth from SHCSession."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession.acquire_information",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "ssl_certificate": "test-cert.pem",
                "ssl_key": "test-key.pem",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_invalid_auth_from_mac(hass):
    """Test we handle invalid auth from invalid mac."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "boschshcpy.session.SHCSession.acquire_information",
        return_value=SHCInformation,
    ), patch(
        "boschshcpy.session.SHCInformation.getMacAddress",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "ssl_certificate": "test-cert.pem",
                "ssl_key": "test-key.pem",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_other_exception(hass):
    """Test we handle exception error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bosch_shc.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "ssl_certificate": "test-cert.pem",
                "ssl_key": "test-key.pem",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
