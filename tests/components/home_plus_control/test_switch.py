"""Test the Legrand Home+ Control switch platform."""
import datetime as dt
from unittest.mock import patch

from homepluscontrol.homeplusapi import HomePlusControlApiError

from homeassistant import config_entries, setup
from homeassistant.components.home_plus_control.const import (
    CONF_SUBSCRIPTION_KEY,
    DOMAIN,
    ENTITY_UIDS,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET

from tests.common import async_fire_time_changed
from tests.components.home_plus_control.conftest import (
    CLIENT_ID,
    CLIENT_SECRET,
    SUBSCRIPTION_KEY,
)


def entity_assertions(
    hass,
    num_exp_entities,
    num_exp_devices=None,
    expected_entities=None,
    expected_devices=None,
):
    """Assert number of entities and devices."""
    entity_reg = hass.helpers.entity_registry.async_get(hass)
    device_reg = hass.helpers.device_registry.async_get(hass)

    if num_exp_devices is None:
        num_exp_devices = num_exp_entities

    assert len(entity_reg.entities.keys()) == num_exp_entities
    assert len(device_reg.devices.keys()) == num_exp_devices

    if expected_entities is not None:
        for exp_entity, present in expected_entities.items():
            assert bool(entity_reg.async_get(exp_entity)) == present

    if expected_devices is not None:
        for exp_device, present in expected_devices.items():
            assert bool(device_reg.async_get(exp_device)) == present


def one_entity_assertion(hass, device_uid, availability):
    """Assert the presence of an entity and its specified availability."""
    entity_reg = hass.helpers.entity_registry.async_get(hass)
    device_reg = hass.helpers.device_registry.async_get(hass)

    device_id = device_reg.async_get_device({(DOMAIN, device_uid)}).id
    device_entities = hass.helpers.entity_registry.async_entries_for_device(
        entity_reg, device_id
    )

    assert len(device_entities) == 1
    one_entity = device_entities[0]
    assert (
        hass.data["entity_platform"][DOMAIN][0].entities[one_entity.entity_id].available
        == availability
    )


async def test_plant_update(
    hass,
    mock_config_entry,
    mock_modules,
):
    """Test entity and device loading."""
    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Check the entities and devices
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )


async def test_plant_topology_reduction_change(
    hass,
    mock_config_entry,
    mock_modules,
):
    """Test an entity leaving the plant topology."""
    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Check the entities and devices - 5 mock entities
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # Now we refresh the topology with one entity less
    mock_modules.pop("0000000987654321fedcba")
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        async_fire_time_changed(
            hass, dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=100)
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Check for plant, topology and module status - this time only 4 left
    entity_assertions(
        hass,
        num_exp_entities=4,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": False,
        },
    )


async def test_plant_topology_increase_change(
    hass,
    mock_config_entry,
    mock_modules,
):
    """Test an entity entering the plant topology."""
    # Remove one module initially
    new_module = mock_modules.pop("0000000987654321fedcba")

    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Check the entities and devices - we have 4 entities to start with
    entity_assertions(
        hass,
        num_exp_entities=4,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": False,
        },
    )

    # Now we refresh the topology with one entity more
    mock_modules["0000000987654321fedcba"] = new_module
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        async_fire_time_changed(
            hass, dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=100)
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )


async def test_module_status_unavailable(hass, mock_config_entry, mock_modules):
    """Test a module becoming unreachable in the plant."""
    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Check the entities and devices - 5 mock entities
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # Confirm the availability of this particular entity
    test_entity_uid = "0000000987654321fedcba"
    one_entity_assertion(hass, test_entity_uid, True)

    # Now we refresh the topology with the module being unreachable
    mock_modules["0000000987654321fedcba"].reachable = False

    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        async_fire_time_changed(
            hass, dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=100)
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Assert the devices and entities
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )
    await hass.async_block_till_done()
    # The entity is present, but not available
    one_entity_assertion(hass, test_entity_uid, False)


async def test_module_status_available(
    hass,
    mock_config_entry,
    mock_modules,
):
    """Test a module becoming reachable in the plant."""
    # Set the module initially unreachable
    mock_modules["0000000987654321fedcba"].reachable = False

    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Assert the devices and entities
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # This particular entity is not available
    test_entity_uid = "0000000987654321fedcba"
    one_entity_assertion(hass, test_entity_uid, False)

    # Now we refresh the topology with the module being reachable
    mock_modules["0000000987654321fedcba"].reachable = True
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        async_fire_time_changed(
            hass, dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=100)
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Assert the devices and entities remain the same
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # Now the entity is available
    test_entity_uid = "0000000987654321fedcba"
    one_entity_assertion(hass, test_entity_uid, True)


async def test_initial_api_error(
    hass,
    mock_config_entry,
    mock_modules,
):
    """Test an API error on initial call."""
    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
        side_effect=HomePlusControlApiError,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # The component has been loaded
    assert mock_config_entry.state == config_entries.ENTRY_STATE_LOADED

    # Check the entities and devices - None have been configured
    entity_assertions(hass, num_exp_entities=0)


async def test_update_with_api_error(
    hass,
    mock_config_entry,
    mock_modules,
):
    """Test an API timeout when updating the module data."""
    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # The component has been loaded
    assert mock_config_entry.state == config_entries.ENTRY_STATE_LOADED

    # Check the entities and devices - all entities should be there
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )
    for test_entity_uid in hass.data[DOMAIN]["home_plus_control_entry_id"][ENTITY_UIDS]:
        one_entity_assertion(hass, test_entity_uid, True)

    # Attempt to update the data, but API update fails
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
        side_effect=HomePlusControlApiError,
    ) as mock_check:
        async_fire_time_changed(
            hass, dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=100)
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Assert the devices and entities - all should still be present
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # This entity has not returned a status, so appears as unavailable
    for test_entity_uid in hass.data[DOMAIN]["home_plus_control_entry_id"][ENTITY_UIDS]:
        one_entity_assertion(hass, test_entity_uid, False)
