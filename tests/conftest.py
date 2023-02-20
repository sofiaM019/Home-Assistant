"""Set up some common test helper things."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from contextlib import asynccontextmanager
import datetime
import functools
import gc
import itertools
import logging
import sqlite3
import ssl
import sys
import threading
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import client
from aiohttp.test_utils import (
    BaseTestServer,
    TestClient,
    TestServer,
    make_mocked_request,
)
from aiohttp.typedefs import JSONDecoder
from aiohttp.web import Application
import freezegun
import multidict
import pytest
import pytest_socket
import requests_mock
from syrupy.assertion import SnapshotAssertion

from homeassistant import core as ha, loader, runner, util
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_READ_ONLY
from homeassistant.auth.models import Credentials
from homeassistant.auth.providers import homeassistant, legacy_api_password
from homeassistant.components.device_tracker.legacy import Device
from homeassistant.components.network.models import Adapter, IPv4ConfiguredAddress
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH,
    TYPE_AUTH_OK,
    TYPE_AUTH_REQUIRED,
)
from homeassistant.components.websocket_api.http import URL
from homeassistant.config import YAML_CONFIG_FILE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import HASSIO_USER_NAME
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
    event,
    issue_registry as ir,
    recorder as recorder_helper,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, location
from homeassistant.util.json import json_loads

from .ignore_uncaught_exceptions import IGNORE_UNCAUGHT_EXCEPTIONS
from .syrupy import HomeAssistantSnapshotExtension
from .typing import (
    ClientSessionGenerator,
    MockHAClientWebSocket,
    MqttMockHAClient,
    MqttMockHAClientGenerator,
    MqttMockPahoClient,
    RecorderInstanceGenerator,
    WebSocketGenerator,
)

if TYPE_CHECKING:
    # Local import to avoid processing recorder and SQLite modules when running a
    # testcase which does not use the recorder.
    from homeassistant.components import recorder

pytest.register_assert_rewrite("tests.common")

from .common import (  # noqa: E402, isort:skip
    CLIENT_ID,
    INSTANCES,
    MockConfigEntry,
    MockUser,
    async_fire_mqtt_message,
    async_test_home_assistant,
    get_test_home_assistant,
    init_recorder_component,
    mock_storage,
    patch_yaml_files,
)
from .test_util.aiohttp import (  # noqa: E402, isort:skip
    AiohttpClientMocker,
    mock_aiohttp_client,
)


_LOGGER = logging.getLogger(__name__)

asyncio.set_event_loop_policy(runner.HassEventLoopPolicy(False))
# Disable fixtures overriding our beautiful policy
asyncio.set_event_loop_policy = lambda policy: None

if sys.version_info[:2] >= (3, 11):
    from .asyncio_legacy import legacy_coroutine

    setattr(asyncio, "coroutine", legacy_coroutine)


def _utcnow() -> datetime.datetime:
    """Make utcnow patchable by freezegun."""
    return datetime.datetime.now(datetime.timezone.utc)


dt_util.utcnow = _utcnow  # type: ignore[assignment]
event.time_tracker_utcnow = _utcnow  # type: ignore[assignment]


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom pytest options."""
    parser.addoption("--dburl", action="store", default="sqlite://")


def pytest_configure(config: pytest.Config) -> None:
    """Register marker for tests that log exceptions."""
    config.addinivalue_line(
        "markers", "no_fail_on_log_exception: mark test to not fail on logged exception"
    )
    if config.getoption("verbose") > 0:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def pytest_runtest_setup() -> None:
    """Prepare pytest_socket and freezegun.

    pytest_socket:
    Throw if tests attempt to open sockets.

    allow_unix_socket is set to True because it's needed by asyncio.
    Important: socket_allow_hosts must be called before disable_socket, otherwise all
    destinations will be allowed.

    freezegun:
    Modified to include https://github.com/spulec/freezegun/pull/424
    """
    pytest_socket.socket_allow_hosts(["127.0.0.1"])
    pytest_socket.disable_socket(allow_unix_socket=True)

    freezegun.api.datetime_to_fakedatetime = ha_datetime_to_fakedatetime  # type: ignore[attr-defined]
    freezegun.api.FakeDatetime = HAFakeDatetime  # type: ignore[attr-defined]

    def adapt_datetime(val):
        return val.isoformat(" ")

    # Setup HAFakeDatetime converter for sqlite3
    sqlite3.register_adapter(HAFakeDatetime, adapt_datetime)

    # Setup HAFakeDatetime converter for pymysql
    try:
        # pylint: disable-next=import-outside-toplevel
        import MySQLdb.converters as MySQLdb_converters
    except ImportError:
        pass
    else:
        MySQLdb_converters.conversions[
            HAFakeDatetime
        ] = MySQLdb_converters.DateTime2literal


def ha_datetime_to_fakedatetime(datetime) -> freezegun.api.FakeDatetime:  # type: ignore[name-defined]
    """Convert datetime to FakeDatetime.

    Modified to include https://github.com/spulec/freezegun/pull/424.
    """
    return freezegun.api.FakeDatetime(  # type: ignore[attr-defined]
        datetime.year,
        datetime.month,
        datetime.day,
        datetime.hour,
        datetime.minute,
        datetime.second,
        datetime.microsecond,
        datetime.tzinfo,
        fold=datetime.fold,
    )


class HAFakeDatetime(freezegun.api.FakeDatetime):  # type: ignore[name-defined]
    """Modified to include https://github.com/spulec/freezegun/pull/424."""

    @classmethod
    def now(cls, tz=None):
        """Return frozen now."""
        now = cls._time_to_freeze() or freezegun.api.real_datetime.now()
        if tz:
            result = tz.fromutc(now.replace(tzinfo=tz))
        else:
            result = now

        # Add the _tz_offset only if it's non-zero to preserve fold
        if cls._tz_offset():
            result += cls._tz_offset()

        return ha_datetime_to_fakedatetime(result)


_R = TypeVar("_R")
_P = ParamSpec("_P")


def check_real(func: Callable[_P, Coroutine[Any, Any, _R]]):
    """Force a function to require a keyword _test_real to be passed in."""

    @functools.wraps(func)
    async def guard_func(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        real = kwargs.pop("_test_real", None)

        if not real:
            raise RuntimeError(
                f'Forgot to mock or pass "_test_real=True" to {func.__name__}'
            )

        return await func(*args, **kwargs)

    return guard_func


# Guard a few functions that would make network connections
location.async_detect_location_info = check_real(location.async_detect_location_info)
util.get_local_ip = lambda: "127.0.0.1"


@pytest.fixture(name="caplog")
def caplog_fixture(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Set log level to debug for tests using the caplog fixture."""
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture(autouse=True, scope="module")
def garbage_collection() -> None:
    """Run garbage collection at known locations.

    This is to mimic the behavior of pytest-aiohttp, and is
    required to avoid warnings during garbage collection from
    spilling over into next test case. We run it per module which
    handles the most common cases and let each module override
    to run per test case if needed.
    """
    gc.collect()


@pytest.fixture(autouse=True)
def verify_cleanup(
    event_loop: asyncio.AbstractEventLoop,
) -> Generator[None, None, None]:
    """Verify that the test has cleaned up resources correctly."""
    threads_before = frozenset(threading.enumerate())
    tasks_before = asyncio.all_tasks(event_loop)
    yield

    event_loop.run_until_complete(event_loop.shutdown_default_executor())

    if len(INSTANCES) >= 2:
        count = len(INSTANCES)
        for inst in INSTANCES:
            inst.stop()
        pytest.exit(f"Detected non stopped instances ({count}), aborting test run")

    # Warn and clean-up lingering tasks and timers
    # before moving on to the next test.
    tasks = asyncio.all_tasks(event_loop) - tasks_before
    for task in tasks:
        _LOGGER.warning("Linger task after test %r", task)
        task.cancel()
    if tasks:
        event_loop.run_until_complete(asyncio.wait(tasks))

    for handle in event_loop._scheduled:  # type: ignore[attr-defined]
        if not handle.cancelled():
            _LOGGER.warning("Lingering timer after test %r", handle)
            handle.cancel()

    # Verify no threads where left behind.
    threads = frozenset(threading.enumerate()) - threads_before
    for thread in threads:
        assert isinstance(thread, threading._DummyThread) or thread.name.startswith(
            "waitpid-"
        )


@pytest.fixture(autouse=True)
def bcrypt_cost() -> Generator[None, None, None]:
    """Run with reduced rounds during tests, to speed up uses."""
    import bcrypt

    gensalt_orig = bcrypt.gensalt

    def gensalt_mock(rounds=12, prefix=b"2b"):
        return gensalt_orig(4, prefix)

    bcrypt.gensalt = gensalt_mock
    yield
    bcrypt.gensalt = gensalt_orig


@pytest.fixture
def hass_storage() -> Generator[dict[str, Any], None, None]:
    """Fixture to mock storage."""
    with mock_storage() as stored_data:
        yield stored_data


@pytest.fixture
def load_registries() -> bool:
    """Fixture to control the loading of registries when setting up the hass fixture.

    To avoid loading the registries, tests can be marked with:
    @pytest.mark.parametrize("load_registries", [False])
    """
    return True


class CoalescingResponse(client.ClientWebSocketResponse):
    """ClientWebSocketResponse client that mimics the websocket js code."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Init the ClientWebSocketResponse."""
        super().__init__(*args, **kwargs)
        self._recv_buffer: list[Any] = []

    async def receive_json(
        self,
        *,
        loads: JSONDecoder = json_loads,
        timeout: float | None = None,
    ) -> Any:
        """receive_json or from buffer."""
        if self._recv_buffer:
            return self._recv_buffer.pop(0)
        data = await self.receive_str(timeout=timeout)
        decoded = loads(data)
        if isinstance(decoded, list):
            self._recv_buffer = decoded
            return self._recv_buffer.pop(0)
        return decoded


class CoalescingClient(TestClient):
    """Client that mimics the websocket js code."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Init TestClient."""
        super().__init__(*args, ws_response_class=CoalescingResponse, **kwargs)


@pytest.fixture
def aiohttp_client_cls() -> type[CoalescingClient]:
    """Override the test class for aiohttp."""
    return CoalescingClient


@pytest.fixture
def aiohttp_client(
    event_loop: asyncio.AbstractEventLoop,
) -> Generator[ClientSessionGenerator, None, None]:
    """Override the default aiohttp_client since 3.x does not support aiohttp_client_cls.

    Remove this when upgrading to 4.x as aiohttp_client_cls
    will do the same thing

    aiohttp_client(app, **kwargs)
    aiohttp_client(server, **kwargs)
    aiohttp_client(raw_server, **kwargs)
    """
    loop = event_loop
    clients = []

    async def go(
        __param: Application | BaseTestServer,
        *args: Any,
        server_kwargs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> TestClient:
        if isinstance(__param, Callable) and not isinstance(  # type: ignore[arg-type]
            __param, (Application, BaseTestServer)
        ):
            __param = __param(loop, *args, **kwargs)
            kwargs = {}
        else:
            assert not args, "args should be empty"

        client: TestClient
        if isinstance(__param, Application):
            server_kwargs = server_kwargs or {}
            server = TestServer(__param, loop=loop, **server_kwargs)
            client = CoalescingClient(server, loop=loop, **kwargs)
        elif isinstance(__param, BaseTestServer):
            client = TestClient(__param, loop=loop, **kwargs)
        else:
            raise TypeError("Unknown argument type: %r" % type(__param))

        await client.start_server()
        clients.append(client)
        return client

    yield go

    async def finalize() -> None:
        while clients:
            await clients.pop().close()

    loop.run_until_complete(finalize())


@pytest.fixture
def hass_fixture_setup() -> list[bool]:
    """Fixture which is truthy if the hass fixture has been setup."""
    return []


@pytest.fixture
def hass(
    hass_fixture_setup: list[bool],
    event_loop: asyncio.AbstractEventLoop,
    load_registries: bool,
    hass_storage: dict[str, Any],
    request: pytest.FixtureRequest,
) -> Generator[HomeAssistant, None, None]:
    """Fixture to provide a test instance of Home Assistant."""

    loop = event_loop
    hass_fixture_setup.append(True)

    orig_tz = dt_util.DEFAULT_TIME_ZONE

    def exc_handle(loop, context):
        """Handle exceptions by rethrowing them, which will fail the test."""
        # Most of these contexts will contain an exception, but not all.
        # The docs note the key as "optional"
        # See https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_exception_handler
        if "exception" in context:
            exceptions.append(context["exception"])
        else:
            exceptions.append(
                Exception(
                    "Received exception handler without exception, but with message: %s"
                    % context["message"]
                )
            )
        orig_exception_handler(loop, context)

    exceptions: list[Exception] = []
    hass = loop.run_until_complete(async_test_home_assistant(loop, load_registries))
    ha._cv_hass.set(hass)

    orig_exception_handler = loop.get_exception_handler()
    loop.set_exception_handler(exc_handle)

    yield hass

    loop.run_until_complete(hass.async_stop(force=True))

    # Restore timezone, it is set when creating the hass object
    dt_util.DEFAULT_TIME_ZONE = orig_tz

    for ex in exceptions:
        if (
            request.module.__name__,
            request.function.__name__,
        ) in IGNORE_UNCAUGHT_EXCEPTIONS:
            continue
        raise ex


@pytest.fixture
async def stop_hass(
    event_loop: asyncio.AbstractEventLoop,
) -> AsyncGenerator[None, None]:
    """Make sure all hass are stopped."""
    orig_hass = ha.HomeAssistant

    created = []

    def mock_hass():
        hass_inst = orig_hass()
        created.append(hass_inst)
        return hass_inst

    with patch("homeassistant.core.HomeAssistant", mock_hass):
        yield

    for hass_inst in created:
        if hass_inst.state == ha.CoreState.stopped:
            continue

        with patch.object(hass_inst.loop, "stop"):
            await hass_inst.async_block_till_done()
            await hass_inst.async_stop(force=True)
            await event_loop.shutdown_default_executor()


@pytest.fixture(name="requests_mock")
def requests_mock_fixture() -> Generator[requests_mock.Mocker, None, None]:
    """Fixture to provide a requests mocker."""
    with requests_mock.mock() as m:
        yield m


@pytest.fixture
def aioclient_mock() -> Generator[AiohttpClientMocker, None, None]:
    """Fixture to mock aioclient calls."""
    with mock_aiohttp_client() as mock_session:
        yield mock_session


@pytest.fixture
def mock_device_tracker_conf() -> Generator[list[Device], None, None]:
    """Prevent device tracker from reading/writing data."""
    devices: list[Device] = []

    async def mock_update_config(path: str, dev_id: str, entity: Device) -> None:
        devices.append(entity)

    with patch(
        (
            "homeassistant.components.device_tracker.legacy"
            ".DeviceTracker.async_update_config"
        ),
        side_effect=mock_update_config,
    ), patch(
        "homeassistant.components.device_tracker.legacy.async_load_config",
        side_effect=lambda *args: devices,
    ):
        yield devices


@pytest.fixture
async def hass_admin_credential(
    hass: HomeAssistant, local_auth: homeassistant.HassAuthProvider
) -> Credentials:
    """Provide credentials for admin user."""
    return Credentials(
        id="mock-credential-id",
        auth_provider_type="homeassistant",
        auth_provider_id=None,
        data={"username": "admin"},
        is_new=False,
    )


@pytest.fixture
async def hass_access_token(
    hass: HomeAssistant, hass_admin_user: MockUser, hass_admin_credential: Credentials
) -> str:
    """Return an access token to access Home Assistant."""
    await hass.auth.async_link_user(hass_admin_user, hass_admin_credential)

    refresh_token = await hass.auth.async_create_refresh_token(
        hass_admin_user, CLIENT_ID, credential=hass_admin_credential
    )
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
def hass_owner_user(
    hass: HomeAssistant, local_auth: homeassistant.HassAuthProvider
) -> MockUser:
    """Return a Home Assistant admin user."""
    return MockUser(is_owner=True).add_to_hass(hass)


@pytest.fixture
def hass_admin_user(
    hass: HomeAssistant, local_auth: homeassistant.HassAuthProvider
) -> MockUser:
    """Return a Home Assistant admin user."""
    admin_group = hass.loop.run_until_complete(
        hass.auth.async_get_group(GROUP_ID_ADMIN)
    )
    return MockUser(groups=[admin_group]).add_to_hass(hass)


@pytest.fixture
def hass_read_only_user(
    hass: HomeAssistant, local_auth: homeassistant.HassAuthProvider
) -> MockUser:
    """Return a Home Assistant read only user."""
    read_only_group = hass.loop.run_until_complete(
        hass.auth.async_get_group(GROUP_ID_READ_ONLY)
    )
    return MockUser(groups=[read_only_group]).add_to_hass(hass)


@pytest.fixture
def hass_read_only_access_token(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
    local_auth: homeassistant.HassAuthProvider,
) -> str:
    """Return a Home Assistant read only user."""
    credential = Credentials(
        id="mock-readonly-credential-id",
        auth_provider_type="homeassistant",
        auth_provider_id=None,
        data={"username": "readonly"},
        is_new=False,
    )
    hass_read_only_user.credentials.append(credential)

    refresh_token = hass.loop.run_until_complete(
        hass.auth.async_create_refresh_token(
            hass_read_only_user, CLIENT_ID, credential=credential
        )
    )
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
def hass_supervisor_user(
    hass: HomeAssistant, local_auth: homeassistant.HassAuthProvider
) -> MockUser:
    """Return the Home Assistant Supervisor user."""
    admin_group = hass.loop.run_until_complete(
        hass.auth.async_get_group(GROUP_ID_ADMIN)
    )
    return MockUser(
        name=HASSIO_USER_NAME, groups=[admin_group], system_generated=True
    ).add_to_hass(hass)


@pytest.fixture
def hass_supervisor_access_token(
    hass: HomeAssistant,
    hass_supervisor_user,
    local_auth: homeassistant.HassAuthProvider,
) -> str:
    """Return a Home Assistant Supervisor access token."""
    refresh_token = hass.loop.run_until_complete(
        hass.auth.async_create_refresh_token(hass_supervisor_user)
    )
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
def legacy_auth(
    hass: HomeAssistant,
) -> legacy_api_password.LegacyApiPasswordAuthProvider:
    """Load legacy API password provider."""
    prv = legacy_api_password.LegacyApiPasswordAuthProvider(
        hass,
        hass.auth._store,
        {"type": "legacy_api_password", "api_password": "test-password"},
    )
    hass.auth._providers[(prv.type, prv.id)] = prv
    return prv


@pytest.fixture
def local_auth(hass: HomeAssistant) -> homeassistant.HassAuthProvider:
    """Load local auth provider."""
    prv = homeassistant.HassAuthProvider(
        hass, hass.auth._store, {"type": "homeassistant"}
    )
    hass.loop.run_until_complete(prv.async_initialize())
    hass.auth._providers[(prv.type, prv.id)] = prv
    return prv


@pytest.fixture
def hass_client(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
    socket_enabled: None,
) -> ClientSessionGenerator:
    """Return an authenticated HTTP client."""

    async def auth_client() -> TestClient:
        """Return an authenticated client."""
        return await aiohttp_client(
            hass.http.app, headers={"Authorization": f"Bearer {hass_access_token}"}
        )

    return auth_client


@pytest.fixture
def hass_client_no_auth(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    socket_enabled: None,
) -> ClientSessionGenerator:
    """Return an unauthenticated HTTP client."""

    async def client() -> TestClient:
        """Return an authenticated client."""
        return await aiohttp_client(hass.http.app)

    return client


@pytest.fixture
def current_request() -> Generator[MagicMock, None, None]:
    """Mock current request."""
    with patch("homeassistant.components.http.current_request") as mock_request_context:
        mocked_request = make_mocked_request(
            "GET",
            "/some/request",
            headers={"Host": "example.com"},
            sslcontext=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        )
        mock_request_context.get.return_value = mocked_request
        yield mock_request_context


@pytest.fixture
def current_request_with_host(current_request: MagicMock) -> None:
    """Mock current request with a host header."""
    new_headers = multidict.CIMultiDict(current_request.get.return_value.headers)
    new_headers[config_entry_oauth2_flow.HEADER_FRONTEND_BASE] = "https://example.com"
    current_request.get.return_value = current_request.get.return_value.clone(
        headers=new_headers
    )


@pytest.fixture
def hass_ws_client(
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str | None,
    hass: HomeAssistant,
    socket_enabled: None,
) -> WebSocketGenerator:
    """Websocket client fixture connected to websocket server."""

    async def create_client(
        hass: HomeAssistant = hass, access_token: str | None = hass_access_token
    ) -> MockHAClientWebSocket:
        """Create a websocket client."""
        assert await async_setup_component(hass, "websocket_api", {})
        client = await aiohttp_client(hass.http.app)
        websocket = await client.ws_connect(URL)
        auth_resp = await websocket.receive_json()
        assert auth_resp["type"] == TYPE_AUTH_REQUIRED

        if access_token is None:
            await websocket.send_json({"type": TYPE_AUTH, "access_token": "incorrect"})
        else:
            await websocket.send_json({"type": TYPE_AUTH, "access_token": access_token})

        auth_ok = await websocket.receive_json()
        assert auth_ok["type"] == TYPE_AUTH_OK

        def _get_next_id() -> Generator[int, None, None]:
            i = 0
            while True:
                yield (i := i + 1)

        id_generator = _get_next_id()

        def _send_json_auto_id(data: dict[str, Any]) -> Coroutine[Any, Any, None]:
            data["id"] = next(id_generator)
            return websocket.send_json(data)

        # wrap in client
        wrapped_websocket = cast(MockHAClientWebSocket, websocket)
        wrapped_websocket.client = client
        wrapped_websocket.send_json_auto_id = _send_json_auto_id
        return wrapped_websocket

    return create_client


@pytest.fixture(autouse=True)
def fail_on_log_exception(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fixture to fail if a callback wrapped by catch_log_exception or coroutine wrapped by async_create_catching_coro throws."""
    if "no_fail_on_log_exception" in request.keywords:
        return

    def log_exception(format_err, *args):
        raise

    monkeypatch.setattr("homeassistant.util.logging.log_exception", log_exception)


@pytest.fixture
def mqtt_config_entry_data() -> dict[str, Any] | None:
    """Fixture to allow overriding MQTT config."""
    return None


@pytest.fixture
def mqtt_client_mock(hass: HomeAssistant) -> Generator[MqttMockPahoClient, None, None]:
    """Fixture to mock MQTT client."""

    mid: int = 0

    def get_mid() -> int:
        nonlocal mid
        mid += 1
        return mid

    class FakeInfo:
        """Class to fake MQTT info."""

        def __init__(self, mid: int) -> None:
            self.mid = mid
            self.rc = 0

    with patch("paho.mqtt.client.Client") as mock_client:

        @ha.callback
        def _async_fire_mqtt_message(topic, payload, qos, retain):
            async_fire_mqtt_message(hass, topic, payload, qos, retain)
            mid = get_mid()
            mock_client.on_publish(0, 0, mid)
            return FakeInfo(mid)

        def _subscribe(topic, qos=0):
            mid = get_mid()
            mock_client.on_subscribe(0, 0, mid)
            return (0, mid)

        def _unsubscribe(topic):
            mid = get_mid()
            mock_client.on_unsubscribe(0, 0, mid)
            return (0, mid)

        mock_client = mock_client.return_value
        mock_client.connect.return_value = 0
        mock_client.subscribe.side_effect = _subscribe
        mock_client.unsubscribe.side_effect = _unsubscribe
        mock_client.publish.side_effect = _async_fire_mqtt_message
        yield mock_client


@pytest.fixture
async def mqtt_mock(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_config_entry_data: dict[str, Any] | None,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
) -> AsyncGenerator[MqttMockHAClient, None]:
    """Fixture to mock MQTT component."""
    return await mqtt_mock_entry_no_yaml_config()


@asynccontextmanager
async def _mqtt_mock_entry(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_config_entry_data: dict[str, Any] | None,
) -> AsyncGenerator[MqttMockHAClientGenerator, None]:
    """Fixture to mock a delayed setup of the MQTT config entry."""
    # Local import to avoid processing MQTT modules when running a testcase
    # which does not use MQTT.
    from homeassistant.components import mqtt  # pylint: disable=import-outside-toplevel

    if mqtt_config_entry_data is None:
        mqtt_config_entry_data = {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_BIRTH_MESSAGE: {},
        }

    await hass.async_block_till_done()

    entry = MockConfigEntry(
        data=mqtt_config_entry_data,
        domain=mqtt.DOMAIN,
        title="MQTT",
    )
    entry.add_to_hass(hass)

    real_mqtt = mqtt.MQTT
    real_mqtt_instance = None
    mock_mqtt_instance = None

    async def _setup_mqtt_entry(
        setup_entry: Callable[[HomeAssistant, ConfigEntry], Coroutine[Any, Any, bool]]
    ) -> MagicMock:
        """Set up the MQTT config entry."""
        assert await setup_entry(hass, entry)

        # Assert that MQTT is setup
        assert real_mqtt_instance is not None, "MQTT was not setup correctly"
        mock_mqtt_instance.conf = real_mqtt_instance.conf  # For diagnostics
        mock_mqtt_instance._mqttc = mqtt_client_mock

        # connected set to True to get a more realistic behavior when subscribing
        mock_mqtt_instance.connected = True

        hass.helpers.dispatcher.async_dispatcher_send(mqtt.MQTT_CONNECTED)
        await hass.async_block_till_done()

        return mock_mqtt_instance

    def create_mock_mqtt(*args, **kwargs) -> MqttMockHAClient:
        """Create a mock based on mqtt.MQTT."""
        nonlocal mock_mqtt_instance
        nonlocal real_mqtt_instance
        real_mqtt_instance = real_mqtt(*args, **kwargs)
        mock_mqtt_instance = MqttMockHAClient(
            return_value=real_mqtt_instance,
            spec_set=real_mqtt_instance,
            wraps=real_mqtt_instance,
        )
        return mock_mqtt_instance

    with patch("homeassistant.components.mqtt.MQTT", side_effect=create_mock_mqtt):
        yield _setup_mqtt_entry


@pytest.fixture
def hass_config() -> ConfigType | None:
    """Fixture to parameterize the content of configuration.yaml using mock_yaml_config.

    To set a configuration, tests can be marked with:
    @pytest.mark.parametrize("hass_config", [{integration: {...}}])
    and the `mock_hass_config: None` fixture added to the test parameters.
    """
    return None


@pytest.fixture
def mock_hass_config(
    hass: HomeAssistant, hass_config: ConfigType | None
) -> Generator[None, None, None]:
    """Fixture to mock the content of configuration.yaml.

    Patches homeassistant.config.load_yaml_config_file with `hass_config` parameterized as content.
    """
    with patch("homeassistant.config.load_yaml_config_file", return_value=hass_config):
        yield


@pytest.fixture
def yaml_configuration() -> str | None:
    """Fixture to parameterize the content of a single yaml configuration file.

    To set yaml content, tests can be marked with:
    @pytest.mark.parametrize("yaml_configuration", ["..."])
    and the `mock_yaml_configuration: None` fixture added to the test parameters.
    """
    return None


@pytest.fixture
def yaml_configuration_files(yaml_configuration: str | None) -> dict[str, str] | None:
    """Fixture to parameterize multiple yaml configuration files.

    To set the YAML files to patch, tests can be marked with:
    @pytest.mark.parametrize(
        "yaml_configuration_files", [{"configuration.yaml": "..."}]
    )
    and the `mock_yaml_configuration: None` fixture added to the test parameters.
    """
    return (
        None if yaml_configuration is None else {YAML_CONFIG_FILE: yaml_configuration}
    )


@pytest.fixture
def mock_yaml_configuration(
    hass: HomeAssistant, yaml_configuration_files: dict[str, str] | None
) -> Generator[None, None, None]:
    """Fixture to mock the content of the yaml configuration files.

    Patches yaml configuration files using the `yaml_configuration`
    and `yaml_configuration_files` fixtures.
    """
    with patch_yaml_files(yaml_configuration_files):
        yield


@pytest.fixture
async def mqtt_mock_entry_no_yaml_config(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_config_entry_data: dict[str, Any] | None,
) -> AsyncGenerator[MqttMockHAClientGenerator, None]:
    """Set up an MQTT config entry without MQTT yaml config."""

    async def _async_setup_config_entry(
        hass: HomeAssistant, entry: ConfigEntry
    ) -> bool:
        """Help set up the config entry."""
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return True

    async def _setup_mqtt_entry() -> MqttMockHAClient:
        """Set up the MQTT config entry."""
        return await mqtt_mock_entry(_async_setup_config_entry)

    async with _mqtt_mock_entry(
        hass, mqtt_client_mock, mqtt_config_entry_data
    ) as mqtt_mock_entry:
        yield _setup_mqtt_entry


@pytest.fixture
async def mqtt_mock_entry_with_yaml_config(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_config_entry_data: dict[str, Any] | None,
) -> AsyncGenerator[MqttMockHAClientGenerator, None]:
    """Set up an MQTT config entry with MQTT yaml config."""

    async def _async_do_not_setup_config_entry(
        hass: HomeAssistant, entry: ConfigEntry
    ) -> bool:
        """Do nothing."""
        return True

    async def _setup_mqtt_entry() -> MqttMockHAClient:
        """Set up the MQTT config entry."""
        return await mqtt_mock_entry(_async_do_not_setup_config_entry)

    async with _mqtt_mock_entry(
        hass, mqtt_client_mock, mqtt_config_entry_data
    ) as mqtt_mock_entry:
        yield _setup_mqtt_entry


@pytest.fixture(autouse=True)
def mock_network() -> Generator[None, None, None]:
    """Mock network."""
    mock_adapter = Adapter(
        name="eth0",
        index=0,
        enabled=True,
        auto=True,
        default=True,
        ipv4=[IPv4ConfiguredAddress(address="10.10.10.10", network_prefix=24)],
        ipv6=[],
    )
    with patch(
        "homeassistant.components.network.network.async_load_adapters",
        return_value=[mock_adapter],
    ):
        yield


@pytest.fixture(autouse=True)
def mock_get_source_ip() -> Generator[None, None, None]:
    """Mock network util's async_get_source_ip."""
    with patch(
        "homeassistant.components.network.util.async_get_source_ip",
        return_value="10.10.10.10",
    ):
        yield


@pytest.fixture
def mock_zeroconf() -> Generator[None, None, None]:
    """Mock zeroconf."""
    with patch("homeassistant.components.zeroconf.HaZeroconf", autospec=True), patch(
        "homeassistant.components.zeroconf.HaAsyncServiceBrowser", autospec=True
    ):
        yield


@pytest.fixture
def mock_async_zeroconf(mock_zeroconf: None) -> Generator[None, None, None]:
    """Mock AsyncZeroconf."""
    with patch("homeassistant.components.zeroconf.HaAsyncZeroconf") as mock_aiozc:
        zc = mock_aiozc.return_value
        zc.async_unregister_service = AsyncMock()
        zc.async_register_service = AsyncMock()
        zc.async_update_service = AsyncMock()
        zc.zeroconf.async_wait_for_start = AsyncMock()
        zc.zeroconf.done = False
        zc.async_close = AsyncMock()
        zc.ha_async_close = AsyncMock()
        yield zc


@pytest.fixture
def enable_custom_integrations(hass: HomeAssistant) -> None:
    """Enable custom integrations defined in the test dir."""
    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS)


@pytest.fixture
def enable_statistics() -> bool:
    """Fixture to control enabling of recorder's statistics compilation.

    To enable statistics, tests can be marked with:
    @pytest.mark.parametrize("enable_statistics", [True])
    """
    return False


@pytest.fixture
def enable_statistics_table_validation() -> bool:
    """Fixture to control enabling of recorder's statistics table validation.

    To enable statistics table validation, tests can be marked with:
    @pytest.mark.parametrize("enable_statistics_table_validation", [True])
    """
    return False


@pytest.fixture
def enable_nightly_purge() -> bool:
    """Fixture to control enabling of recorder's nightly purge job.

    To enable nightly purging, tests can be marked with:
    @pytest.mark.parametrize("enable_nightly_purge", [True])
    """
    return False


@pytest.fixture
def recorder_config() -> dict[str, Any] | None:
    """Fixture to override recorder config.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("recorder_config", [{...}])
    """
    return None


@pytest.fixture
def recorder_db_url(
    pytestconfig: pytest.Config,
    hass_fixture_setup: list[bool],
) -> Generator[str, None, None]:
    """Prepare a default database for tests and return a connection URL."""
    assert not hass_fixture_setup

    db_url = cast(str, pytestconfig.getoption("dburl"))
    if db_url.startswith("mysql://"):
        # pylint: disable-next=import-outside-toplevel
        import sqlalchemy_utils

        charset = "utf8mb4' COLLATE = 'utf8mb4_unicode_ci"
        assert not sqlalchemy_utils.database_exists(db_url)
        sqlalchemy_utils.create_database(db_url, encoding=charset)
    elif db_url.startswith("postgresql://"):
        # pylint: disable-next=import-outside-toplevel
        import sqlalchemy_utils

        assert not sqlalchemy_utils.database_exists(db_url)
        sqlalchemy_utils.create_database(db_url, encoding="utf8")
    yield db_url
    if db_url.startswith("mysql://"):
        # pylint: disable-next=import-outside-toplevel
        import sqlalchemy as sa

        made_url = sa.make_url(db_url)
        db = made_url.database
        engine = sa.create_engine(db_url)
        # Check for any open connections to the database before dropping it
        # to ensure that InnoDB does not deadlock.
        with engine.begin() as connection:
            query = sa.text(
                "select id FROM information_schema.processlist WHERE db=:db and id != CONNECTION_ID()"
            )
            rows = connection.execute(query, parameters={"db": db}).fetchall()
            if rows:
                raise RuntimeError(
                    f"Unable to drop database {db} because it is in use by {rows}"
                )
        engine.dispose()
        sqlalchemy_utils.drop_database(db_url)
    elif db_url.startswith("postgresql://"):
        sqlalchemy_utils.drop_database(db_url)


@pytest.fixture
def hass_recorder(
    recorder_db_url: str,
    enable_nightly_purge: bool,
    enable_statistics: bool,
    enable_statistics_table_validation: bool,
    hass_storage,
) -> Generator[Callable[..., HomeAssistant], None, None]:
    """Home Assistant fixture with in-memory recorder."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components import recorder

    original_tz = dt_util.DEFAULT_TIME_ZONE

    hass = get_test_home_assistant()
    nightly = recorder.Recorder.async_nightly_tasks if enable_nightly_purge else None
    stats = recorder.Recorder.async_periodic_statistics if enable_statistics else None
    stats_validate = (
        recorder.statistics.validate_db_schema
        if enable_statistics_table_validation
        else itertools.repeat(set())
    )
    with patch(
        "homeassistant.components.recorder.Recorder.async_nightly_tasks",
        side_effect=nightly,
        autospec=True,
    ), patch(
        "homeassistant.components.recorder.Recorder.async_periodic_statistics",
        side_effect=stats,
        autospec=True,
    ), patch(
        "homeassistant.components.recorder.migration.statistics_validate_db_schema",
        side_effect=stats_validate,
        autospec=True,
    ):

        def setup_recorder(config: dict[str, Any] | None = None) -> HomeAssistant:
            """Set up with params."""
            init_recorder_component(hass, config, recorder_db_url)
            hass.start()
            hass.block_till_done()
            hass.data[recorder.DATA_INSTANCE].block_till_done()
            return hass

        yield setup_recorder
        hass.stop()

    # Restore timezone, it is set when creating the hass object
    dt_util.DEFAULT_TIME_ZONE = original_tz


async def _async_init_recorder_component(
    hass: HomeAssistant,
    add_config: dict[str, Any] | None = None,
    db_url: str | None = None,
) -> None:
    """Initialize the recorder asynchronously."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components import recorder

    config = dict(add_config) if add_config else {}
    if recorder.CONF_DB_URL not in config:
        config[recorder.CONF_DB_URL] = db_url
        if recorder.CONF_COMMIT_INTERVAL not in config:
            config[recorder.CONF_COMMIT_INTERVAL] = 0

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True):
        if recorder.DOMAIN not in hass.data:
            recorder_helper.async_initialize_recorder(hass)
        assert await async_setup_component(
            hass, recorder.DOMAIN, {recorder.DOMAIN: config}
        )
        assert recorder.DOMAIN in hass.config.components
    _LOGGER.info(
        "Test recorder successfully started, database location: %s",
        config[recorder.CONF_DB_URL],
    )


@pytest.fixture
async def async_setup_recorder_instance(
    recorder_db_url: str,
    enable_nightly_purge: bool,
    enable_statistics: bool,
    enable_statistics_table_validation: bool,
) -> AsyncGenerator[RecorderInstanceGenerator, None]:
    """Yield callable to setup recorder instance."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components import recorder

    # pylint: disable-next=import-outside-toplevel
    from .components.recorder.common import async_recorder_block_till_done

    nightly = recorder.Recorder.async_nightly_tasks if enable_nightly_purge else None
    stats = recorder.Recorder.async_periodic_statistics if enable_statistics else None
    stats_validate = (
        recorder.statistics.validate_db_schema
        if enable_statistics_table_validation
        else itertools.repeat(set())
    )
    with patch(
        "homeassistant.components.recorder.Recorder.async_nightly_tasks",
        side_effect=nightly,
        autospec=True,
    ), patch(
        "homeassistant.components.recorder.Recorder.async_periodic_statistics",
        side_effect=stats,
        autospec=True,
    ), patch(
        "homeassistant.components.recorder.migration.statistics_validate_db_schema",
        side_effect=stats_validate,
        autospec=True,
    ):

        async def async_setup_recorder(
            hass: HomeAssistant, config: ConfigType | None = None
        ) -> recorder.Recorder:
            """Setup and return recorder instance."""  # noqa: D401
            await _async_init_recorder_component(hass, config, recorder_db_url)
            await hass.async_block_till_done()
            instance = hass.data[recorder.DATA_INSTANCE]
            # The recorder's worker is not started until Home Assistant is running
            if hass.state == CoreState.running:
                await async_recorder_block_till_done(hass)
            return instance

        yield async_setup_recorder


@pytest.fixture
async def recorder_mock(
    recorder_config: dict[str, Any] | None,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
) -> recorder.Recorder:
    """Fixture with in-memory recorder."""
    return await async_setup_recorder_instance(hass, recorder_config)


@pytest.fixture
def mock_integration_frame() -> Generator[Mock, None, None]:
    """Mock as if we're calling code from inside an integration."""
    correct_frame = Mock(
        filename="/home/paulus/homeassistant/components/hue/light.py",
        lineno="23",
        line="self.light.is_on",
    )
    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            correct_frame,
            Mock(
                filename="/home/paulus/aiohue/lights.py",
                lineno="2",
                line="something()",
            ),
        ],
    ):
        yield correct_frame


@pytest.fixture(name="enable_bluetooth")
async def mock_enable_bluetooth(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> AsyncGenerator[None, None]:
    """Fixture to mock starting the bleak scanner."""
    entry = MockConfigEntry(domain="bluetooth", unique_id="00:00:00:00:00:01")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    yield
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def mock_bluetooth_adapters() -> Generator[None, None, None]:
    """Fixture to mock bluetooth adapters."""
    with patch(
        "bluetooth_adapters.systems.platform.system", return_value="Linux"
    ), patch("bluetooth_adapters.systems.linux.LinuxAdapters.refresh"), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.adapters",
        {
            "hci0": {
                "address": "00:00:00:00:00:01",
                "hw_version": "usb:v1D6Bp0246d053F",
                "passive_scan": False,
                "sw_version": "homeassistant",
                "manufacturer": "ACME",
                "product": "Bluetooth Adapter 5.0",
                "product_id": "aa01",
                "vendor_id": "cc01",
            },
        },
    ):
        yield


@pytest.fixture
def mock_bleak_scanner_start() -> Generator[MagicMock, None, None]:
    """Fixture to mock starting the bleak scanner."""

    # Late imports to avoid loading bleak unless we need it

    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.bluetooth import scanner as bluetooth_scanner

    # We need to drop the stop method from the object since we patched
    # out start and this fixture will expire before the stop method is called
    # when EVENT_HOMEASSISTANT_STOP is fired.
    bluetooth_scanner.OriginalBleakScanner.stop = AsyncMock()  # type: ignore[assignment]
    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
    ) as mock_bleak_scanner_start:
        yield mock_bleak_scanner_start


@pytest.fixture
def mock_bluetooth(
    mock_bleak_scanner_start: MagicMock, mock_bluetooth_adapters: None
) -> None:
    """Mock out bluetooth from starting."""


@pytest.fixture
def area_registry(hass: HomeAssistant) -> ar.AreaRegistry:
    """Return the area registry from the current hass instance."""
    return ar.async_get(hass)


@pytest.fixture
def device_registry(hass: HomeAssistant) -> dr.DeviceRegistry:
    """Return the device registry from the current hass instance."""
    return dr.async_get(hass)


@pytest.fixture
def entity_registry(hass: HomeAssistant) -> er.EntityRegistry:
    """Return the entity registry from the current hass instance."""
    return er.async_get(hass)


@pytest.fixture
def issue_registry(hass: HomeAssistant) -> ir.IssueRegistry:
    """Return the issue registry from the current hass instance."""
    return ir.async_get(hass)


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Return snapshot assertion fixture with the Home Assistant extension."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)
