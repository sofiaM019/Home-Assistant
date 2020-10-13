"""Test the Foscam config flow."""
from unittest.mock import patch

from libpyfoscam.foscam import ERROR_FOSCAM_AUTH, ERROR_FOSCAM_UNAVAILABLE

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.foscam import config_flow

from tests.common import MockConfigEntry

VALID_CONFIG = {
    config_flow.CONF_HOST: "10.0.0.2",
    config_flow.CONF_PORT: 88,
    config_flow.CONF_USERNAME: "admin",
    config_flow.CONF_PASSWORD: "1234",
    config_flow.CONF_STREAM: "Main",
}
CAMERA_NAME = "Mocked Foscam Camera"
CAMERA_MAC = "C0:C1:D0:F4:B4:D4"


def setup_mock_foscam_camera(mock_foscam_camera):
    """Mock FoscamCamera simulating behaviour using a base valid config."""

    def configure_mock_on_init(host, port, user, passwd, verbose=False):
        return_code = 0
        data = {}

        if (
            host != VALID_CONFIG[config_flow.CONF_HOST]
            or port != VALID_CONFIG[config_flow.CONF_PORT]
        ):
            return_code = ERROR_FOSCAM_UNAVAILABLE

        elif (
            user != VALID_CONFIG[config_flow.CONF_USERNAME]
            or passwd != VALID_CONFIG[config_flow.CONF_PASSWORD]
        ):
            return_code = ERROR_FOSCAM_AUTH

        else:
            data["devName"] = CAMERA_NAME
            data["mac"] = CAMERA_MAC

        mock_foscam_camera.get_dev_info.return_value = (return_code, data)

        return mock_foscam_camera

    mock_foscam_camera.side_effect = configure_mock_on_init


async def test_user_valid(hass):
    """Test valid config from user input."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera, patch(
        "homeassistant.components.foscam.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.foscam.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        setup_mock_foscam_camera(mock_foscam_camera)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == CAMERA_NAME
        assert result["data"] == VALID_CONFIG

        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


async def test_user_invalid_auth(hass):
    """Test we handle invalid auth from user input."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)

        invalid_user = VALID_CONFIG.copy()
        invalid_user[config_flow.CONF_USERNAME] = "invalid"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            invalid_user,
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_user_cannot_connect(hass):
    """Test we handle cannot connect error from user input."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)

        invalid_host = VALID_CONFIG.copy()
        invalid_host[config_flow.CONF_HOST] = "127.0.0.1"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            invalid_host,
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_user_already_configured(hass):
    """Test we handle already configured from user input."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN, data=VALID_CONFIG, unique_id=CAMERA_MAC
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_import_user_valid(hass):
    """Test valid config from import."""
    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera, patch(
        "homeassistant.components.foscam.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.foscam.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        setup_mock_foscam_camera(mock_foscam_camera)

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=VALID_CONFIG,
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == CAMERA_NAME
        assert result["data"] == VALID_CONFIG

        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


async def test_import_user_valid_with_name(hass):
    """Test valid config with extra name from import."""
    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera, patch(
        "homeassistant.components.foscam.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.foscam.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        setup_mock_foscam_camera(mock_foscam_camera)

        name = CAMERA_NAME + " 1234"
        with_name = VALID_CONFIG.copy()
        with_name[config_flow.CONF_NAME] = name

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=with_name,
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == name
        assert result["data"] == VALID_CONFIG

        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


async def test_import_invalid_auth(hass):
    """Test we handle invalid auth from import."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN, data=VALID_CONFIG, unique_id=CAMERA_MAC
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)

        invalid_user = VALID_CONFIG.copy()
        invalid_user[config_flow.CONF_USERNAME] = "invalid"

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=invalid_user,
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "invalid_auth"


async def test_import_cannot_connect(hass):
    """Test we handle invalid auth from import."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN, data=VALID_CONFIG, unique_id=CAMERA_MAC
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)

        invalid_host = VALID_CONFIG.copy()
        invalid_host[config_flow.CONF_HOST] = "127.0.0.1"

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=invalid_host,
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "cannot_connect"


async def test_import_already_configured(hass):
    """Test we handle already configured from import."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN, data=VALID_CONFIG, unique_id=CAMERA_MAC
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=VALID_CONFIG,
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"
