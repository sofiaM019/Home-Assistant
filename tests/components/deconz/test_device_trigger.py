"""deCONZ device automation tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.deconz import device_trigger
from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.deconz.device_trigger import CONF_SUBTYPE
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.common import (
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture
def automation_calls(hass):
    """Track automation calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass, aioclient_mock):
    """Test triggers work."""
    data = {
        "sensors": {
            "1": {
                "config": {
                    "alert": "none",
                    "battery": 60,
                    "group": "10",
                    "on": True,
                    "reachable": True,
                },
                "ep": 1,
                "etag": "1b355c0b6d2af28febd7ca9165881952",
                "manufacturername": "IKEA of Sweden",
                "mode": 1,
                "modelid": "TRADFRI on/off switch",
                "name": "TRÅDFRI on/off switch ",
                "state": {"buttonevent": 2002, "lastupdated": "2019-09-07T07:39:39"},
                "swversion": "1.4.018",
                "type": "ZHASwitch",
                "uniqueid": "d0:cf:5e:ff:fe:71:a4:3a-01-1000",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")}
    )

    assert device_trigger._get_deconz_event_from_device_id(hass, device.id)

    triggers = await async_get_device_automations(hass, "trigger", device.id)

    expected_triggers = [
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
            CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_LONG_PRESS,
            CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_LONG_RELEASE,
            CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
            CONF_SUBTYPE: device_trigger.CONF_TURN_OFF,
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_LONG_PRESS,
            CONF_SUBTYPE: device_trigger.CONF_TURN_OFF,
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_LONG_RELEASE,
            CONF_SUBTYPE: device_trigger.CONF_TURN_OFF,
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: SENSOR_DOMAIN,
            ATTR_ENTITY_ID: "sensor.tradfri_on_off_switch_battery_level",
            CONF_PLATFORM: "device",
            CONF_TYPE: ATTR_BATTERY_LEVEL,
        },
    ]

    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_manage_unsupported_remotes(hass, aioclient_mock):
    """Verify no triggers for an unsupported remote."""
    data = {
        "sensors": {
            "1": {
                "config": {
                    "alert": "none",
                    "group": "10",
                    "on": True,
                    "reachable": True,
                },
                "ep": 1,
                "etag": "1b355c0b6d2af28febd7ca9165881952",
                "manufacturername": "IKEA of Sweden",
                "mode": 1,
                "modelid": "Unsupported model",
                "name": "TRÅDFRI on/off switch ",
                "state": {"buttonevent": 2002, "lastupdated": "2019-09-07T07:39:39"},
                "swversion": "1.4.018",
                "type": "ZHASwitch",
                "uniqueid": "d0:cf:5e:ff:fe:71:a4:3a-01-1000",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")}
    )

    assert device_trigger._get_deconz_event_from_device_id(hass, device.id)

    triggers = await async_get_device_automations(hass, "trigger", device.id)

    expected_triggers = []

    assert_lists_same(triggers, expected_triggers)


async def test_functional_device_trigger(
    hass, aioclient_mock, mock_deconz_websocket, automation_calls
):
    """Test proper matching and attachment of device trigger automation."""
    await async_setup_component(hass, "persistent_notification", {})

    data = {
        "sensors": {
            "1": {
                "config": {
                    "alert": "none",
                    "battery": 60,
                    "group": "10",
                    "on": True,
                    "reachable": True,
                },
                "ep": 1,
                "etag": "1b355c0b6d2af28febd7ca9165881952",
                "manufacturername": "IKEA of Sweden",
                "mode": 1,
                "modelid": "TRADFRI on/off switch",
                "name": "TRÅDFRI on/off switch ",
                "state": {"buttonevent": 2002, "lastupdated": "2019-09-07T07:39:39"},
                "swversion": "1.4.018",
                "type": "ZHASwitch",
                "uniqueid": "d0:cf:5e:ff:fe:71:a4:3a-01-1000",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")}
    )

    trigger_config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DECONZ_DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
        CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
    }

    assert await device_trigger.async_validate_trigger_config(hass, trigger_config)

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": trigger_config,
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"buttonevent": 1002},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert len(automation_calls) == 1
    assert automation_calls[0].data["some"] == "test_trigger_button_press"


async def test_validate_trigger_unknown_device(
    hass, aioclient_mock, mock_deconz_websocket, automation_calls
):
    """Test unknown device does not return a trigger config."""
    await setup_deconz_integration(hass, aioclient_mock)

    trigger_config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DECONZ_DOMAIN,
        CONF_DEVICE_ID: "unknown device",
        CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
        CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
    }

    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_validate_trigger_config(hass, trigger_config)

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": trigger_config,
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(automation_calls) == 0


async def test_validate_trigger_unsupported_device(
    hass, aioclient_mock, mock_deconz_websocket, automation_calls
):
    """Test unsupported device doesn't return a trigger config."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")},
        model="unsupported",
    )

    trigger_config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DECONZ_DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
        CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
    }

    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_validate_trigger_config(hass, trigger_config)

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": trigger_config,
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(automation_calls) == 0


async def test_validate_trigger_unsupported_trigger(
    hass, aioclient_mock, mock_deconz_websocket, automation_calls
):
    """Test unsupported trigger does not return a trigger config."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")},
        model="TRADFRI on/off switch",
    )

    trigger_config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DECONZ_DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: "unsupported",
        CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
    }

    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_validate_trigger_config(hass, trigger_config)

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": trigger_config,
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(automation_calls) == 0


async def test_attach_trigger_no_matching_event(
    hass, aioclient_mock, mock_deconz_websocket, automation_calls
):
    """Test no matching event for device doesn't return a trigger config."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")},
        model="TRADFRI on/off switch",
    )

    trigger_config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DECONZ_DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
        CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
    }

    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_attach_trigger(hass, trigger_config, None, None)

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": trigger_config,
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(automation_calls) == 0


async def test_helper_no_match(hass, aioclient_mock):
    """Verify trigger helper returns None when no event could be matched."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert not device_trigger._get_deconz_event_from_device_id(hass, "mock-id")


async def test_helper_no_gateway_exist(hass):
    """Verify trigger helper returns None when no gateway exist."""
    assert not device_trigger._get_deconz_event_from_device_id(hass, "mock-id")
