"""Test different accessory types: Fans."""
from collections import namedtuple

import pytest

from homeassistant.components.fan import (
    ATTR_DIRECTION, ATTR_OSCILLATING, ATTR_SPEED,
    DIRECTION_FORWARD, DIRECTION_REVERSE, DOMAIN, SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION, SPEED_HIGH, SPEED_LOW, SPEED_MEDIUM, SPEED_OFF,
    SUPPORT_DIRECTION, SUPPORT_OSCILLATE, SUPPORT_SET_SPEED)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES,
    STATE_ON, STATE_OFF, STATE_UNKNOWN, SERVICE_TURN_ON, SERVICE_TURN_OFF)

from tests.common import async_mock_service
from tests.components.homekit.test_accessories import patch_debounce


@pytest.fixture(scope='module')
def cls(request):
    """Patch debounce decorator during import of type_fans."""
    patcher = patch_debounce()
    patcher.start()
    _import = __import__('homeassistant.components.homekit.type_fans',
                         fromlist=['Fan'])
    request.addfinalizer(patcher.stop)
    patcher_tuple = namedtuple('Cls', ['fan'])
    return patcher_tuple(fan=_import.Fan)


async def test_fan_basic(hass, cls):
    """Test fan with char state."""
    entity_id = 'fan.demo'

    hass.states.async_set(entity_id, STATE_ON,
                          {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    acc = cls.fan(hass, 'Fan', entity_id, 2, None)

    assert acc.aid == 2
    assert acc.category == 3  # Fan
    assert acc.char_active.value == 0

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_active.value == 1

    hass.states.async_set(entity_id, STATE_OFF,
                          {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    call_turn_off = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)

    await hass.async_add_job(acc.char_active.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()

    await hass.async_add_job(acc.char_active.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id


async def test_fan_speed(hass, cls):
    """Test fan with speed."""
    entity_id = 'fan.demo'

    hass.states.async_set(entity_id, STATE_ON, {
        ATTR_SUPPORTED_FEATURES: SUPPORT_SET_SPEED,
        ATTR_SPEED: SPEED_LOW})
    await hass.async_block_till_done()
    acc = cls.fan(hass, 'Fan', entity_id, 2, None)

    assert acc.char_speed.value == 0

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_speed.value == 33

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SPEED: SPEED_MEDIUM})
    await hass.async_block_till_done()
    assert acc.char_speed.value == 66

    hass.states.async_set(entity_id, STATE_OFF, {ATTR_SPEED: SPEED_OFF})
    await hass.async_block_till_done()
    assert acc.char_speed.value == 0

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SPEED: 'invalid'})
    await hass.async_block_till_done()
    assert acc.char_speed.value == 0

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SPEED: SPEED_HIGH})
    await hass.async_block_till_done()
    assert acc.char_speed.value == 100

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    call_turn_off = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)

    await hass.async_add_job(acc.char_speed.client_update_value, 25)
    await hass.async_block_till_done()
    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_SPEED] == SPEED_LOW

    await hass.async_add_job(acc.char_speed.client_update_value, 50)
    await hass.async_block_till_done()
    assert call_turn_on[1]
    assert call_turn_on[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[1].data[ATTR_SPEED] == SPEED_MEDIUM

    await hass.async_add_job(acc.char_active.client_update_value, 1)
    await hass.async_block_till_done()
    assert len(call_turn_on) == 2

    await hass.async_add_job(acc.char_speed.client_update_value, 75)
    await hass.async_block_till_done()
    assert call_turn_on[2]
    assert call_turn_on[2].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[2].data[ATTR_SPEED] == SPEED_HIGH

    await hass.async_add_job(acc.char_speed.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id


async def test_fan_direction(hass, cls):
    """Test fan with direction."""
    entity_id = 'fan.demo'

    hass.states.async_set(entity_id, STATE_ON, {
        ATTR_SUPPORTED_FEATURES: SUPPORT_DIRECTION,
        ATTR_DIRECTION: DIRECTION_FORWARD})
    await hass.async_block_till_done()
    acc = cls.fan(hass, 'Fan', entity_id, 2, None)

    assert acc.char_direction.value == 0

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_direction.value == 0

    hass.states.async_set(entity_id, STATE_ON,
                          {ATTR_DIRECTION: DIRECTION_REVERSE})
    await hass.async_block_till_done()
    assert acc.char_direction.value == 1

    # Set from HomeKit
    call_set_direction = async_mock_service(hass, DOMAIN,
                                            SERVICE_SET_DIRECTION)

    await hass.async_add_job(acc.char_direction.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_set_direction[0]
    assert call_set_direction[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[0].data[ATTR_DIRECTION] == DIRECTION_FORWARD

    await hass.async_add_job(acc.char_direction.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_set_direction[1]
    assert call_set_direction[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[1].data[ATTR_DIRECTION] == DIRECTION_REVERSE


async def test_fan_oscillate(hass, cls):
    """Test fan with oscillate."""
    entity_id = 'fan.demo'

    hass.states.async_set(entity_id, STATE_ON, {
        ATTR_SUPPORTED_FEATURES: SUPPORT_OSCILLATE, ATTR_OSCILLATING: False})
    await hass.async_block_till_done()
    acc = cls.fan(hass, 'Fan', entity_id, 2, None)

    assert acc.char_swing.value == 0

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_swing.value == 0

    hass.states.async_set(entity_id, STATE_ON,
                          {ATTR_OSCILLATING: True})
    await hass.async_block_till_done()
    assert acc.char_swing.value == 1

    # Set from HomeKit
    call_oscillate = async_mock_service(hass, DOMAIN, SERVICE_OSCILLATE)

    await hass.async_add_job(acc.char_swing.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_oscillate[0]
    assert call_oscillate[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[0].data[ATTR_OSCILLATING] is False

    await hass.async_add_job(acc.char_swing.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_oscillate[1]
    assert call_oscillate[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[1].data[ATTR_OSCILLATING] is True
