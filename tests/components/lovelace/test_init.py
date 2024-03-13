"""Test the Lovelace initialization."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


@pytest.fixture
def mock_onboarding_not_done() -> Generator[MagicMock, None, None]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=False,
    ) as mock_onboarding:
        yield mock_onboarding


@pytest.fixture
def mock_onboarding_done() -> Generator[MagicMock, None, None]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=True,
    ) as mock_onboarding:
        yield mock_onboarding


async def test_create_dashboards_when_onboarded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    mock_onboarding_done,
) -> None:
    """Test we don't create dashboards when onboarded."""
    client = await hass_ws_client(hass)

    assert await async_setup_component(hass, "lovelace", {})

    # List dashboards
    await client.send_json_auto_id({"type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []


async def test_create_dashboards_when_not_onboarded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    mock_onboarding_not_done,
) -> None:
    """Test we automatically create dashboards when not onboarded."""
    client = await hass_ws_client(hass)

    assert await async_setup_component(hass, "lovelace", {})

    # List dashboards
    await client.send_json_auto_id({"type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "id": "map",
            "title": "Map",
            "url_path": "map",
            "mode": "storage",
            "require_admin": False,
            "show_in_sidebar": True,
        }
    ]

    # List map dashboard config
    await client.send_json_auto_id({"type": "lovelace/config", "url_path": "map"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"strategy": {"type": "map"}}
