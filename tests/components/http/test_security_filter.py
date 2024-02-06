"""Test security filter middleware."""
import asyncio
from http import HTTPStatus

from aiohttp import web
import pytest
import urllib3

from homeassistant.components.http.security_filter import setup_security_filter

from tests.typing import ClientSessionGenerator


async def mock_handler(request):
    """Return OK."""
    return web.Response(text="OK")


@pytest.mark.parametrize(
    ("request_path", "request_params"),
    [
        ("/", {}),
        ("/lovelace/dashboard", {}),
        ("/frontend_latest/chunk.4c9e2d8dc10f77b885b0.js", {}),
        ("/static/translations/en-f96a262a5a6eede29234dc45dc63abf2.json", {}),
        ("/", {"test": "123"}),
    ],
)
async def test_ok_requests(
    request_path, request_params, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test request paths that should not be filtered."""
    app = web.Application()
    app.router.add_get("/{all:.*}", mock_handler)

    setup_security_filter(app)

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(request_path, params=request_params)

    assert resp.status == HTTPStatus.OK
    assert await resp.text() == "OK"


@pytest.mark.parametrize(
    ("request_path", "request_params", "fail_on_query_string"),
    [
        ("/proc/self/environ", {}),
        ("/", {"test": "/test/../../api"}),
        ("/", {"test": "test/../../api"}),
        ("/", {"test": "/test/%2E%2E%2f%2E%2E%2fapi"}),
        ("/", {"test": "test/%2E%2E%2f%2E%2E%2fapi"}),
        ("/", {"test": "test/%252E%252E/api"}),
        ("/", {"test": "test/%252E%252E%2fapi"}),
        (
            "/",
            {"test": "test/%2525252E%2525252E%2525252f%2525252E%2525252E%2525252fapi"},
        ),
        ("/test/.%252E/api", {}),
        ("/test/%252E%252E/api", {}),
        ("/test/%2E%2E%2f%2E%2E%2fapi", {}),
        ("/test/%2525252E%2525252E%2525252f%2525252E%2525252E/api", {}),
        ("/", {"sql": ";UNION SELECT (a, b"}),
        ("/", {"sql": "UNION%20SELECT%20%28a%2C%20b"}),
        ("/UNION%20SELECT%20%28a%2C%20b", {}),
        ("/", {"sql": "concat(..."}),
        ("/", {"xss": "<script >"}),
        ("/<script >", {"xss": ""}),
        ("/%3Cscript%3E", {}),
    ],
)
async def test_bad_requests(
    request_path,
    request_params,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test request paths that should be filtered."""
    app = web.Application()
    app.router.add_get("/{all:.*}", mock_handler)

    setup_security_filter(app)

    mock_api_client = await aiohttp_client(app)

    # Manual params handling
    if request_params:
        raw_params = "&".join(f"{val}={key}" for val, key in request_params.items())
        man_params = f"?{raw_params}"
    else:
        man_params = ""

    http = urllib3.PoolManager()
    resp = await asyncio.get_running_loop().run_in_executor(
        None,
        http.request,
        "GET",
        f"http://{mock_api_client.host}:{mock_api_client.port}{request_path}{man_params}",
        request_params,
    )

    assert resp.status == HTTPStatus.BAD_REQUEST

    message = "Filtered a potential harmful request to:"
    assert message in caplog.text


@pytest.mark.parametrize(
    ("request_path", "request_params"),
    [
        ("/some\thing", {}),
        ("/new\nline/cinema", {}),
        ("/return\r/to/sender", {}),
        ("/", {"some": "\thing"}),
        ("/", {"\newline": "cinema"}),
        ("/", {"return": "t\rue"}),
    ],
)
async def test_ok_requests_with_encoded_unsafe_bytes(
    request_path,
    request_params,
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """Test request with unsafe bytes in their URLs, sent with urllib3 so they are safely encoded."""
    app = web.Application()
    app.router.add_get("/{all:.*}", mock_handler)

    setup_security_filter(app)

    mock_api_client = await aiohttp_client(app)

    # Manual params handling
    if request_params:
        raw_params = "&".join(f"{val}={key}" for val, key in request_params.items())
        man_params = f"?{raw_params}"
    else:
        man_params = ""

    http = urllib3.PoolManager()
    resp = await asyncio.get_running_loop().run_in_executor(
        None,
        http.request,
        "GET",
        f"http://{mock_api_client.host}:{mock_api_client.port}{request_path}{man_params}",
        request_params,
    )

    assert resp.status == HTTPStatus.OK


@pytest.mark.parametrize(
    ("request_path", "request_params"),
    [
        ("/some\thing", {}),
        ("/new\nline/cinema", {}),
        ("/return\r/to/sender", {}),
        ("/", {"some": "\thing"}),
        ("/", {"\newline": "cinema"}),
        ("/", {"return": "t\rue"}),
    ],
)
async def test_bad_requests_with_unsafe_bytes(
    request_path,
    request_params,
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """Test request with unsafe bytes in their URLs."""
    app = web.Application()
    app.router.add_get("/{all:.*}", mock_handler)

    setup_security_filter(app)

    mock_api_client = await aiohttp_client(app)

    # Manual params handling
    if request_params:
        raw_params = "&".join(f"{val}={key}" for val, key in request_params.items())
        man_params = f"?{raw_params}"
    else:
        man_params = ""

    reader, writer = await asyncio.open_connection(
        mock_api_client.host, mock_api_client.port
    )

    request = f"GET {request_path}{man_params} HTTP/1.1\r\nHost: {mock_api_client.host}\r\n\r\n"
    writer.write(request.encode())

    data = await reader.readuntil(b"\r\n")
    response_line = data.decode()

    writer.close()
    await writer.wait_closed()

    # Parse the status code
    status_code = int(response_line.split(" ")[1])
    assert status_code == HTTPStatus.BAD_REQUEST
