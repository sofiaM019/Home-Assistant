"""Helper for aiohttp webclient stuff."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from ssl import SSLContext
import sys
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

import aiohttp
from aiohttp import web
from aiohttp.hdrs import CONTENT_TYPE, USER_AGENT
from aiohttp.web_exceptions import HTTPBadGateway, HTTPGatewayTimeout
import async_timeout

from homeassistant import config_entries
from homeassistant.const import APPLICATION_NAME, EVENT_HOMEASSISTANT_CLOSE, __version__
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.loader import bind_hass
from homeassistant.util import ssl as ssl_util

from .frame import warn_use
from .json import json_dumps, json_loads

if TYPE_CHECKING:
    from aiohttp.typedefs import JSONDecoder


DATA_CONNECTOR = "aiohttp_connector"
DATA_CONNECTOR_NOTVERIFY = "aiohttp_connector_notverify"
DATA_CLIENTSESSION = "aiohttp_clientsession"
DATA_CLIENTSESSION_NOTVERIFY = "aiohttp_clientsession_notverify"
SERVER_SOFTWARE = "{0}/{1} aiohttp/{2} Python/{3[0]}.{3[1]}".format(
    APPLICATION_NAME, __version__, aiohttp.__version__, sys.version_info
)

WARN_CLOSE_MSG = "closes the Home Assistant aiohttp session"


class HassClientResponse(aiohttp.ClientResponse):
    """aiohttp.ClientResponse with a json method that uses json_loads by default."""

    async def json(
        self,
        *args: Any,
        loads: JSONDecoder = json_loads,
        **kwargs: Any,
    ) -> Any:
        """Send a json request and parse the json response."""
        return await super().json(*args, loads=loads, **kwargs)


@callback
@bind_hass
def async_get_clientsession(
    hass: HomeAssistant, verify_ssl: bool = True
) -> aiohttp.ClientSession:
    """Return default aiohttp ClientSession.

    This method must be run in the event loop.
    """
    key = DATA_CLIENTSESSION if verify_ssl else DATA_CLIENTSESSION_NOTVERIFY

    if key not in hass.data:
        hass.data[key] = _async_create_clientsession(
            hass,
            verify_ssl,
            auto_cleanup_method=_async_register_default_clientsession_shutdown,
        )

    return cast(aiohttp.ClientSession, hass.data[key])


@callback
@bind_hass
def async_create_clientsession(
    hass: HomeAssistant,
    ssl_context: bool | SSLContext = True,
    auto_cleanup: bool = True,
    **kwargs: Any,
) -> aiohttp.ClientSession:
    """Create a new ClientSession with kwargs, i.e. for cookies.

    If auto_cleanup is False, you need to call detach() after the session
    returned is no longer used. Default is True, the session will be
    automatically detached on homeassistant_stop or when being created
    in config entry setup, the config entry is unloaded.

    This method must be run in the event loop.
    """
    auto_cleanup_method = None
    if auto_cleanup:
        auto_cleanup_method = _async_register_clientsession_shutdown

    clientsession = _async_create_clientsession(
        hass,
        ssl_context,
        auto_cleanup_method=auto_cleanup_method,
        **kwargs,
    )

    return clientsession


@callback
def _async_create_clientsession(
    hass: HomeAssistant,
    ssl_context: bool | SSLContext = True,
    auto_cleanup_method: Callable[[HomeAssistant, aiohttp.ClientSession], None]
    | None = None,
    **kwargs: Any,
) -> aiohttp.ClientSession:
    """Create a new ClientSession with kwargs, i.e. for cookies."""
    clientsession = aiohttp.ClientSession(
        connector=_async_get_connector(hass, ssl_context),
        json_serialize=json_dumps,
        response_class=HassClientResponse,
        **kwargs,
    )
    # Prevent packages accidentally overriding our default headers
    # It's important that we identify as Home Assistant
    # If a package requires a different user agent, override it by passing a headers
    # dictionary to the request method.
    # pylint: disable=protected-access
    clientsession._default_headers = MappingProxyType({USER_AGENT: SERVER_SOFTWARE})  # type: ignore[assignment]

    clientsession.close = warn_use(clientsession.close, WARN_CLOSE_MSG)  # type: ignore[assignment]

    if auto_cleanup_method:
        auto_cleanup_method(hass, clientsession)

    return clientsession


@bind_hass
async def async_aiohttp_proxy_web(
    hass: HomeAssistant,
    request: web.BaseRequest,
    web_coro: Awaitable[aiohttp.ClientResponse],
    buffer_size: int = 102400,
    timeout: int = 10,
) -> web.StreamResponse | None:
    """Stream websession request to aiohttp web response."""
    try:
        async with async_timeout.timeout(timeout):
            req = await web_coro

    except asyncio.CancelledError:
        # The user cancelled the request
        return None

    except asyncio.TimeoutError as err:
        # Timeout trying to start the web request
        raise HTTPGatewayTimeout() from err

    except aiohttp.ClientError as err:
        # Something went wrong with the connection
        raise HTTPBadGateway() from err

    try:
        return await async_aiohttp_proxy_stream(
            hass, request, req.content, req.headers.get(CONTENT_TYPE)
        )
    finally:
        req.close()


@bind_hass
async def async_aiohttp_proxy_stream(
    hass: HomeAssistant,
    request: web.BaseRequest,
    stream: aiohttp.StreamReader,
    content_type: str | None,
    buffer_size: int = 102400,
    timeout: int = 10,
) -> web.StreamResponse:
    """Stream a stream to aiohttp web response."""
    response = web.StreamResponse()
    if content_type is not None:
        response.content_type = content_type
    await response.prepare(request)

    # Suppressing something went wrong fetching data, closed connection
    with suppress(asyncio.TimeoutError, aiohttp.ClientError):
        while hass.is_running:
            async with async_timeout.timeout(timeout):
                data = await stream.read(buffer_size)

            if not data:
                break
            await response.write(data)

    return response


@callback
def _async_register_clientsession_shutdown(
    hass: HomeAssistant, clientsession: aiohttp.ClientSession
) -> None:
    """Register ClientSession close on Home Assistant shutdown or config entry unload.

    This method must be run in the event loop.
    """

    @callback
    def _async_close_websession(*_: Any) -> None:
        """Close websession."""
        clientsession.detach()

    unsub = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_CLOSE, _async_close_websession
    )

    if not (config_entry := config_entries.current_entry.get()):
        return

    config_entry.async_on_unload(unsub)
    config_entry.async_on_unload(_async_close_websession)


@callback
def _async_register_default_clientsession_shutdown(
    hass: HomeAssistant, clientsession: aiohttp.ClientSession
) -> None:
    """Register default ClientSession close on Home Assistant shutdown.

    This method must be run in the event loop.
    """

    @callback
    def _async_close_websession(event: Event) -> None:
        """Close websession."""
        clientsession.detach()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_websession)


@callback
def _async_get_connector(
    hass: HomeAssistant, ssl_context: bool | SSLContext = True
) -> aiohttp.BaseConnector:
    """Return the connector pool for aiohttp.

    This method must be run in the event loop.
    """
    key = None
    if isinstance(ssl_context, bool):
        key = DATA_CONNECTOR if ssl_context else DATA_CONNECTOR_NOTVERIFY

        if key in hass.data:
            return cast(aiohttp.BaseConnector, hass.data[key])

    if ssl_context is True:
        ssl_context = ssl_util.client_context()

    connector = aiohttp.TCPConnector(enable_cleanup_closed=True, ssl=ssl_context)
    if key is not None:
        hass.data[key] = connector

    async def _async_close_connector(event: Event) -> None:
        """Close connector pool."""
        await connector.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_connector)

    return connector
