"""Tests for samsungtv Components."""
import asyncio
from asynctest import mock
import pytest
import samsungctl
from tests.common import MockDependency
from unittest.mock import call, patch

from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SUPPORT_TURN_ON,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_URL,
)
from homeassistant.components.samsungtv.const import DOMAIN as SAMSUNGTV_DOMAIN
from homeassistant.components.samsungtv.media_player import (
    CONF_TIMEOUT,
    SUPPORT_SAMSUNGTV,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PORT,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNKNOWN,
)
from homeassistant.setup import async_setup_component


ENTITY_ID = f"{DOMAIN}.fake"
MOCK_CONFIG = {
    DOMAIN: {
        CONF_PLATFORM: SAMSUNGTV_DOMAIN,
        CONF_HOST: "fake",
        CONF_NAME: "fake",
        CONF_PORT: 8001,
        CONF_TIMEOUT: 10,
        CONF_MAC: "fake",
    }
}

ENTITY_ID_NOMAC = f"{DOMAIN}.fake_nomac"
MOCK_CONFIG_NOMAC = {
    DOMAIN: {
        CONF_PLATFORM: SAMSUNGTV_DOMAIN,
        CONF_HOST: "fake_nomac",
        CONF_NAME: "fake_nomac",
        CONF_PORT: 55000,
        CONF_TIMEOUT: 10,
    }
}

ENTITY_ID_AUTO = f"{DOMAIN}.fake_auto"
MOCK_CONFIG_AUTO = {
    DOMAIN: {
        CONF_PLATFORM: SAMSUNGTV_DOMAIN,
        CONF_HOST: "fake_auto",
        CONF_NAME: "fake_auto",
    }
}

MOCK_DISCOVERY = {
    "discovery": {"name": "[TV]fake2", "model_name": "fake2", "host": "fake2"}
}

AUTODETECT_WEBSOCKET = {
    "name": "HomeAssistant",
    "description": "fake_auto",
    "id": "ha.component.samsung",
    "method": "websocket",
    "port": None,
    "host": "fake_auto",
    "timeout": 1,
}
AUTODETECT_LEGACY = {
    "name": "HomeAssistant",
    "description": "fake_auto",
    "id": "ha.component.samsung",
    "method": "legacy",
    "port": None,
    "host": "fake_auto",
    "timeout": 1,
}


class AccessDenied(Exception):
    """Dummy Exception."""


class ConnectionClosed(Exception):
    """Dummy Exception."""


class UnhandledResponse(Exception):
    """Dummy Exception."""


@pytest.fixture(name="remote")
def remote_fixture():
    """Patch the samsungctl Remote."""
    with patch("samsungctl.Remote") as remote_class, patch(
        "samsungctl.exceptions"
    ) as exceptions_class, patch(
        "homeassistant.components.samsungtv.media_player.socket"
    ) as socket_class:
        remote = mock.Mock()
        remote_class.return_value = remote
        exceptions_class.AccessDenied = AccessDenied
        exceptions_class.ConnectionClosed = ConnectionClosed
        exceptions_class.UnhandledResponse = UnhandledResponse
        socket = mock.Mock()
        socket_class.return_value = socket
        yield remote


@pytest.fixture(name="wakeonlan")
def wakeonlan_fixture():
    """Patch the wakeonlan Remote."""
    with MockDependency("wakeonlan") as wakeonlan:
        yield wakeonlan


async def setup_samsungtv(hass, config):
    """Set up mock Samsung TV."""
    await async_setup_component(hass, "media_player", config)
    await hass.async_block_till_done()


async def test_setup_with_mac(hass, remote):
    """Test setup of platform."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert hass.states.get(ENTITY_ID)


async def test_setup_without_mac(hass, remote):
    """Test setup of platform."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOMAC)
    assert hass.states.get(ENTITY_ID_NOMAC)


async def test_setup_discovery(hass, remote):
    """Test setup of platform with discovery."""
    # await setup_samsungtv(hass, MOCK_DISCOVERY)
    # assert hass.states.get("media_player.fake2")
    assert False


async def test_update_on(hass, remote):
    """Testing update tv on."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    # await async_update()
    assert STATE_ON == state.state


async def test_update_off(hass, remote):
    """Testing update tv off."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    remote.control = mock.Mock(side_effect=OSError("Boom"))
    # await async_update()
    assert STATE_OFF == state.state


async def test_send_key(hass, remote, wakeonlan):
    """Test for send key."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and async_update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_VOLUP"), call("KEY")]
    assert STATE_ON == state.state


async def test_send_key_autodetect_websocket(hass):
    """Test for send key with autodetection of protocol."""
    with patch("samsungctl.Remote") as remote, patch(
        "homeassistant.components.samsungtv.media_player.socket"
    ):
        await setup_samsungtv(hass, MOCK_CONFIG_AUTO)
        state = hass.states.get(ENTITY_ID_AUTO)
        assert await hass.services.async_call(
            DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID_AUTO}, True
        )
        assert remote.control.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_WEBSOCKET)]
        assert STATE_ON == state.state


async def test_send_key_autodetect_legacy(hass):
    """Test for send key with autodetection of protocol."""
    with patch(
        "samsungctl.Remote", side_effect=[OSError("Boom"), mock.DEFAULT]
    ) as remote, patch("homeassistant.components.samsungtv.media_player.socket"):
        await setup_samsungtv(hass, MOCK_CONFIG_AUTO)
        state = hass.states.get(ENTITY_ID_AUTO)
        assert await hass.services.async_call(
            DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID_AUTO}, True
        )
        assert remote.call_count == 2
        assert remote.call_args_list == [
            call(AUTODETECT_WEBSOCKET),
            call(AUTODETECT_LEGACY),
        ]
        assert STATE_ON == state.state


async def test_send_key_autodetect_none(hass):
    """Test for send key with autodetection of protocol."""
    with patch("samsungctl.Remote", side_effect=OSError("Boom")) as remote, patch(
        "homeassistant.components.samsungtv.media_player.socket"
    ):
        await setup_samsungtv(hass, MOCK_CONFIG_AUTO)
        state = hass.states.get(ENTITY_ID_AUTO)
        assert await hass.services.async_call(
            DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID_AUTO}, True
        )
        # 4 calls because of retry
        assert remote.call_count == 4
        assert remote.call_args_list == [
            call(AUTODETECT_WEBSOCKET),
            call(AUTODETECT_LEGACY),
            call(AUTODETECT_WEBSOCKET),
            call(AUTODETECT_LEGACY),
        ]
        assert STATE_UNKNOWN == state.state


async def test_send_key_broken_pipe(hass, remote):
    """Testing broken pipe Exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    remote.control = mock.Mock(side_effect=BrokenPipeError("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert STATE_ON == state.state


async def test_send_key_connection_closed_retry_succeed(hass, remote):
    """Test retry on connection closed."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    remote.control = mock.Mock(side_effect=[ConnectionClosed("Boom"), mock.DEFAULT])
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert STATE_ON == state.state
    # verify that _remote.control() get called twice because of retry logic
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_VOLUP"), call("KEY_VOLUP")]


async def test_send_key_unhandled_response(hass, remote):
    """Testing unhandled response exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    remote.control = mock.Mock(
        side_effect=samsungctl.exceptions.UnhandledResponse("Boom")
    )
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert STATE_ON == state.state


async def test_send_key_os_error(hass, remote):
    """Testing broken pipe Exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    remote.control = mock.Mock(side_effect=OSError("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert STATE_OFF == state.state


async def test_name(hass, remote):
    """Test for name property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert "fake" == state.attributes[ATTR_FRIENDLY_NAME]


async def test_state_with_mac(hass, remote, wakeonlan):
    """Test for state property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert STATE_ON == state.state
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert STATE_OFF == state.state


async def test_state_without_mac(hass, remote):
    """Test for state property."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOMAC)
    state = hass.states.get(ENTITY_ID_NOMAC)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID_NOMAC}, True
    )
    assert STATE_ON == state.state
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID_NOMAC}, True
    )
    assert STATE_OFF == state.state


async def test_is_volume_muted(hass, remote):
    """Test for is_volume_muted property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert not state.attributes[ATTR_MEDIA_VOLUME_MUTED]
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        True,
    )
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED]
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        True,
    )
    assert not state.attributes[ATTR_MEDIA_VOLUME_MUTED]


async def test_supported_features_with_mac(hass, remote):
    """Test for supported_features property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert (
        SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON == state.attributes[ATTR_SUPPORTED_FEATURES]
    )


async def test_supported_features_without_mac(hass, remote):
    """Test for supported_features property."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOMAC)
    state = hass.states.get(ENTITY_ID_NOMAC)
    assert SUPPORT_SAMSUNGTV == state.attributes[ATTR_SUPPORTED_FEATURES]


async def test_turn_off_websocket(hass, remote):
    """Test for turn_off."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_POWER")]


async def test_turn_off_legacy(hass, remote):
    """Test for turn_off."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOMAC)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID_NOMAC}, True
    )
    # key called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_POWEROFF")]


async def test_turn_off_os_error(hass, remote):
    """Test for turn_off with OSError."""
    with patch(
        "homeassistant.components.samsungtv.media_player.LOGGER.debug"
    ) as mocked_debug:
        await setup_samsungtv(hass, MOCK_CONFIG)
        remote.close = mock.Mock(side_effect=OSError("BOOM"))
        assert await hass.services.async_call(
            DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
        )
        mocked_debug.assert_called_once_with("Could not establish connection.")


async def test_volume_up(hass, remote):
    """Test for volume_up."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and async_update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_VOLUP"), call("KEY")]


async def test_volume_down(hass, remote):
    """Test for volume_down."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_DOWN, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and async_update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_VOLDOWN"), call("KEY")]


async def test_mute_volume(hass, remote):
    """Test for mute_volume."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        True,
    )
    # key and async_update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_MUTE"), call("KEY")]


async def test_media_play_pause(hass, remote):
    """Test for media_next_track."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PLAY, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_PAUSED
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING


async def test_media_play(hass, remote):
    """Test for media_play."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PLAY, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and async_update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_PLAY"), call("KEY")]


async def test_media_pause(hass, remote):
    """Test for media_pause."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and async_update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_PAUSE"), call("KEY")]


async def test_media_next_track(hass, remote):
    """Test for media_next_track."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_NEXT_TRACK, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and async_update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_FF"), call("KEY")]


async def test_media_previous_track(hass, remote):
    """Test for media_previous_track."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and async_update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_REWIND"), call("KEY")]


async def test_turn_on_with_mac(hass, remote, wakeonlan):
    """Test turn on."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and async_update called
    assert wakeonlan.send_magic_packet.call_count == 1
    assert wakeonlan.send_magic_packet.call_args_list == [call("fake")]


async def test_turn_on_without_mac(hass, remote):
    """Test turn on."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOMAC)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID_NOMAC}, True
    )
    # nothing called as not supported feature
    assert remote.control.call_count == 0


async def test_play_media(hass, remote):
    """Test for play_media."""
    asyncio_sleep = asyncio.sleep
    sleeps = []

    async def sleep(duration, loop):
        sleeps.append(duration)
        await asyncio_sleep(0, loop=loop)

    await setup_samsungtv(hass, MOCK_CONFIG)
    with patch("asyncio.sleep", new=sleep):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_CHANNEL,
                ATTR_MEDIA_CONTENT_ID: "576",
            },
            True,
        )
        # keys and async_update called
        assert remote.control.call_count == 5
        assert remote.control.call_args_list == [
            call("KEY_5"),
            call("KEY_7"),
            call("KEY_6"),
            call("KEY_ENTER"),
            call("KEY"),
        ]
        assert len(sleeps) == 3


async def test_play_media_invalid_type(hass, remote):
    """Test for play_media with invalid media type."""
    url = "https://example.com"
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_URL,
            ATTR_MEDIA_CONTENT_ID: url,
        },
        True,
    )
    # only async_update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY")]


async def test_play_media_channel_as_string(hass, remote):
    """Test for play_media with invalid channel as string."""
    url = "https://example.com"
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_CHANNEL,
            ATTR_MEDIA_CONTENT_ID: url,
        },
        True,
    )
    # only async_update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY")]


async def test_play_media_channel_as_non_positive(hass, remote):
    """Test for play_media with invalid channel as non positive integer."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_CHANNEL,
            ATTR_MEDIA_CONTENT_ID: "-4",
        },
        True,
    )
    # only async_update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY")]


async def test_select_source(hass, remote):
    """Test for select_source."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "HDMI"},
        True,
    )
    # key and async_update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_HDMI"), call("KEY")]


async def test_select_source_invalid_source(hass, remote):
    """Test for select_source with invalid source."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "INVALID"},
        True,
    )
    # only async_update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY")]
