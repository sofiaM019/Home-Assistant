"""Tests for Transmission init."""

from unittest.mock import MagicMock, patch

import pytest
from transmission_rpc.error import TransmissionError

from homeassistant.components import transmission
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.transmission.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_api():
    """Mock an api."""
    with patch("transmission_rpc.Client") as api:
        yield api


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test settings up integration from config entry."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.LOADED


async def test_setup_failed_connection_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test integration failed due to connection error."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    mock_api.side_effect = TransmissionError("111: Connection refused")

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_failed_auth_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test integration failed due to invalid credentials error."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    mock_api.side_effect = TransmissionError("401: Unauthorized")

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data[DOMAIN]


@pytest.mark.parametrize(
    ("domain", "old_unique_id", "new_unique_id"),
    [
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Down Speed", "1234-download"),
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Up Speed", "1234-upload"),
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Status", "1234-status"),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Active Torrents",
            "1234-active_torrents",
        ),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Paused Torrents",
            "1234-paused_torrents",
        ),
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Total Torrents", "1234-total_torrents"),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Completed Torrents",
            "1234-completed_torrents",
        ),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Started Torrents",
            "1234-started_torrents",
        ),
        (SENSOR_DOMAIN, "0.0.0.0-download", "0.0.0.0-download"),
        (SENSOR_DOMAIN, "abcde", "abcde"),
        (SWITCH_DOMAIN, "0.0.0.0-Transmission Switch", "1234-on_off"),
        (SWITCH_DOMAIN, "0.0.0.0-Transmission Turtle Mode", "1234-turtle_mode"),
        (SWITCH_DOMAIN, "0.0.0.0-on_off", "0.0.0.0-on_off"),
        (SWITCH_DOMAIN, "abcde", "abcde"),
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant, domain: str, old_unique_id: str, new_unique_id: str
) -> None:
    """Test unique id migration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA, entry_id="1234")
    entry.add_to_hass(hass)

    ent_reg = er.async_get(hass)

    entity: er.RegistryEntry = ent_reg.async_get_or_create(
        suggested_object_id=f"my_{domain}",
        disabled_by=None,
        domain=domain,
        platform=transmission.DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    migrated_entity = ent_reg.async_get(entity.entity_id)

    assert migrated_entity
    assert migrated_entity.unique_id == new_unique_id
