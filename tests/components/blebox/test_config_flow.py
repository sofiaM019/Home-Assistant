"""Test Home Assistant config flow for BleBox devices."""

from asynctest import CoroutineMock, PropertyMock, mock, patch
import blebox_uniapi
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.blebox import config_flow
from homeassistant.setup import async_setup_component

from .conftest import mock_config, mock_only_feature, setup_product_mock


@pytest.fixture
def flow(hass):
    """Return a user configuration flow."""
    flow = config_flow.BleBoxConfigFlow()
    flow.hass = hass
    flow.context = {"source": config_entries.SOURCE_USER}
    return flow


def create_valid_feature_mock(path="homeassistant.components.blebox.Products"):
    """Return a valid, complete BleBox feature mock."""
    feature = mock_only_feature(
        blebox_uniapi.cover.Cover,
        unique_id="BleBox-gateBox-1afe34db9437-0.position",
        full_name="gateBox-0.position",
        device_class="gate",
        state=0,
        async_update=CoroutineMock(),
        current=None,
    )

    product = setup_product_mock("covers", [feature], path)

    type(product).name = PropertyMock(return_value="My gate controller")
    type(product).model = PropertyMock(return_value="gateController")
    type(product).type = PropertyMock(return_value="gateBox")
    type(product).brand = PropertyMock(return_value="BleBox")
    type(product).firmware_version = PropertyMock(return_value="1.23")
    type(product).unique_id = PropertyMock(return_value="abcd0123ef5678")

    return feature


@pytest.fixture
def valid_feature_mock():
    """Return a valid, complete BleBox feature mock."""
    return create_valid_feature_mock()


@pytest.fixture
def flow_feature_mock():
    """Return a mocked user flow feature."""
    return create_valid_feature_mock(
        "homeassistant.components.blebox.config_flow.Products"
    )


async def test_flow_works(flow, flow_feature_mock):
    """Test that config flow works."""

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await flow.async_step_user(
        {config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "My gate controller"
    assert result["data"] == {
        config_flow.CONF_HOST: "172.2.3.4",
        config_flow.CONF_PORT: 80,
    }


@pytest.fixture
def product_class_mock():
    """Return a mocked feature."""
    path = "homeassistant.components.blebox.config_flow.Products"
    patcher = patch(path, mock.DEFAULT, blebox_uniapi.products.Products, True, True)
    yield patcher


async def test_flow_with_connection_failure(flow, product_class_mock):
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = CoroutineMock(
            side_effect=blebox_uniapi.error.ConnectionError
        )
        result = await flow.async_step_user()
        result = await flow.async_step_user({"host": "172.2.3.4", "port": 80})
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_with_api_failure(flow, product_class_mock):
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = CoroutineMock(
            side_effect=blebox_uniapi.error.Error
        )
        result = await flow.async_step_user()
        result = await flow.async_step_user({"host": "172.2.3.4", "port": 80})
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_with_unknown_failure(flow, product_class_mock):
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = CoroutineMock(side_effect=RuntimeError)

        result = await flow.async_step_user()
        result = await flow.async_step_user({"host": "172.2.3.4", "port": 80})
        assert result["errors"] == {"base": "unknown"}


async def test_flow_with_unsupported_version(flow, product_class_mock):
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = CoroutineMock(
            side_effect=blebox_uniapi.error.UnsupportedBoxVersion
        )

        result = await flow.async_step_user()
        result = await flow.async_step_user({"host": "172.2.3.4", "port": 80})
        assert result["errors"] == {"base": "unsupported_version"}


async def test_async_setup(hass):
    """Test async_setup (for coverage)."""
    assert await async_setup_component(hass, "blebox", {"host": "172.2.3.4"})
    await hass.async_block_till_done()


async def test_already_configured(hass, valid_feature_mock):
    """Test that same device cannot be added twice."""

    config = mock_config("172.1.2.3")
    config.add_to_hass(hass)

    await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        "blebox", context={"source": "user"}, data={"host": "172.1.2.3", "port": 80},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "address_already_configured"


async def test_async_setup_entry(hass, valid_feature_mock):
    """Test async_setup_entry (for coverage)."""

    config = mock_config()
    config.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()
    expected = [config]
    assert expected == hass.config_entries.async_entries()
    assert config.state == config_entries.ENTRY_STATE_LOADED


async def test_async_remove_entry(hass, valid_feature_mock):
    """Test async_setup_entry (for coverage)."""

    config = mock_config()
    config.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_remove(config.entry_id)
    await hass.async_block_till_done()
    expected = []
    assert expected == hass.config_entries.async_entries()
    assert config.state == config_entries.ENTRY_STATE_NOT_LOADED
