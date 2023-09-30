"""Test the init functions for AEH."""
from datetime import timedelta
import logging
from unittest.mock import patch

from azure.kusto.data.exceptions import KustoAuthenticationError, KustoServiceError
import pytest

from homeassistant.components import azure_data_explorer
from homeassistant.components.azure_data_explorer.const import (
    CONF_SEND_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .conftest import FilterTest
from .const import (
    AZURE_DATA_EXPLORER_PATH,
    BASE_CONFIG_FULL,
    BASIC_OPTIONS,
    IMPORT_CONFIG,
)

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_put_event_on_queue_with_managed_client(
    hass,
    entry_managed,
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data,
) -> None:
    # pylint: disable=protected-access
    """Test listening to events from Hass. and writing to ADX with managed client."""

    hass.states.async_set("sensor.test_sensor", STATE_ON)

    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=entry_managed.options[CONF_SEND_INTERVAL])
    )

    await hass.async_block_till_done()
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.assert_called_once()


async def test_put_event_on_queue_with_managed_client_with_error_KustoServiceError(
    hass,
    entry_managed,
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data,
) -> None:
    # pylint: disable=protected-access
    """Test listening to events from Hass. and writing to ADX with managed client with error KustoServiceError."""

    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.side_effect = (
        KustoServiceError("test")
    )

    hass.states.async_set("sensor.test_sensor", STATE_ON)

    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=entry_managed.options[CONF_SEND_INTERVAL])
    )

    await hass.async_block_till_done()
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.assert_called_once()


async def test_put_event_on_queue_with_managed_client_with_error_KustoAuthenticationError(
    hass,
    entry_managed,
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data,
) -> None:
    # pylint: disable=protected-access
    """Test listening to events from Hass. and writing to ADX with managed client with error KustoAuthenticationError."""

    hass.states.async_set("sensor.test_sensor", STATE_ON)

    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=entry_managed.options[CONF_SEND_INTERVAL])
    )

    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.side_effect = (
        KustoAuthenticationError("test", Exception)
    )

    await hass.async_block_till_done()
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.assert_called_once()


# async def test_put_event_on_queue_with_managed_client_with_error_Exception(
#     hass,
#     entry_managed,
#     mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data,
# ) -> None:
#     # pylint: disable=protected-access
#     """Test listening to events from Hass. and writing to ADX with managed client with error Exception."""

#     hass.states.async_set("sensor.test_sensor", STATE_ON)

#     async_fire_time_changed(
#         hass, utcnow() + timedelta(seconds=entry_managed.options[CONF_SEND_INTERVAL])
#     )

#     mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.side_effect = (
#         Exception("test")
#     )

#     await hass.async_block_till_done()
#     mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.assert_called_once()


async def test_put_event_on_queue_with_queueing_client(
    hass,
    entry_queued,
    mock_azure_data_explorer_QueuedIngestClient_ingest_data,
) -> None:
    # pylint: disable=protected-access
    """Test listening to events from Hass. and writing to ADX with managed client."""

    hass.states.async_set("sensor.test_sensor", STATE_ON)

    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=entry_queued.options[CONF_SEND_INTERVAL])
    )

    await hass.async_block_till_done()
    mock_azure_data_explorer_QueuedIngestClient_ingest_data.assert_called_once()


async def test_import(hass) -> None:
    """Test the popping of the filter and further import of the config."""
    config = {
        DOMAIN: {
            "filter": {
                "include_domains": ["light"],
                "include_entity_globs": ["sensor.included_*"],
                "include_entities": ["binary_sensor.included"],
                "exclude_domains": ["light"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
        }
    }
    config[DOMAIN].update(IMPORT_CONFIG)
    assert await async_setup_component(hass, DOMAIN, config)


async def test_filter_only_config(hass) -> None:
    """Test the popping of the filter and further import of the config."""
    config = {
        DOMAIN: {
            "filter": {
                "include_domains": ["light"],
                "include_entity_globs": ["sensor.included_*"],
                "include_entities": ["binary_sensor.included"],
                "exclude_domains": ["light"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)


async def test_unload_entry(
    hass,
    entry_managed,
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data,
) -> None:
    """Test being able to unload an entry.

    Queue should be empty, so adding events to the batch should not be called,
    this verifies that the unload, calls async_stop, which calls async_send and
    shuts down the hub.
    """
    assert await hass.config_entries.async_unload(entry_managed.entry_id)
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.assert_not_called()
    assert entry_managed.state == ConfigEntryState.NOT_LOADED


async def test_failed_test_connection_KustoServiceError(
    hass, mock_execute_query
) -> None:
    """Test Error when no getting proper connection with KustoServiceError."""

    mock_execute_query.side_effect = KustoServiceError("test")

    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_failed_test_connection_KustoAuthenticationError(
    hass, mock_execute_query
) -> None:
    """Test Error when no getting proper connection with KustoAuthenticationError."""
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    mock_execute_query.side_effect = KustoAuthenticationError("test", Exception)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_failed_test_connection_Exception(hass, mock_execute_query) -> None:
    """Test Error when no getting proper connection with Exception."""
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    mock_execute_query.side_effect = Exception
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_late_event(
    hass,
    entry_with_one_event,
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data,
) -> None:
    """Test the check on late events."""
    with patch(
        f"{AZURE_DATA_EXPLORER_PATH}.utcnow",
        return_value=utcnow() + timedelta(hours=1),
    ):
        async_fire_time_changed(
            hass,
            utcnow()
            + timedelta(seconds=entry_with_one_event.options[CONF_SEND_INTERVAL]),
        )
        await hass.async_block_till_done()
        mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.add.assert_not_called()


@pytest.mark.parametrize(
    ("filter_schema", "tests"),
    [
        (
            {
                "include_domains": ["light"],
                "include_entity_globs": ["sensor.included_*"],
                "include_entities": ["binary_sensor.included"],
            },
            [
                FilterTest("climate.excluded", 0),
                FilterTest("light.included", 1),
                FilterTest("sensor.excluded_test", 0),
                FilterTest("sensor.included_test", 1),
                FilterTest("binary_sensor.included", 1),
                FilterTest("binary_sensor.excluded", 0),
            ],
        ),
        (
            {
                "exclude_domains": ["climate"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
            [
                FilterTest("climate.excluded", 0),
                FilterTest("light.included", 1),
                FilterTest("sensor.excluded_test", 0),
                FilterTest("sensor.included_test", 1),
                FilterTest("binary_sensor.included", 1),
                FilterTest("binary_sensor.excluded", 0),
            ],
        ),
        (
            {
                "include_domains": ["light"],
                "include_entity_globs": ["*.included_*"],
                "exclude_domains": ["climate"],
                "exclude_entity_globs": ["*.excluded_*"],
                "exclude_entities": ["light.excluded"],
            },
            [
                FilterTest("light.included", 1),
                FilterTest("light.excluded_test", 0),
                FilterTest("light.excluded", 0),
                FilterTest("sensor.included_test", 1),
                FilterTest("climate.included_test", 1),
            ],
        ),
        (
            {
                "include_entities": ["climate.included", "sensor.excluded_test"],
                "exclude_domains": ["climate"],
                "exclude_entity_globs": ["*.excluded_*"],
                "exclude_entities": ["light.excluded"],
            },
            [
                FilterTest("climate.excluded", 0),
                FilterTest("climate.included", 1),
                FilterTest("switch.excluded_test", 0),
                FilterTest("sensor.excluded_test", 1),
                FilterTest("light.excluded", 0),
                FilterTest("light.included", 1),
            ],
        ),
    ],
    ids=["allowlist", "denylist", "filtered_allowlist", "filtered_denylist"],
)
async def test_filter(
    hass,
    entry_managed,
    tests,
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data,
) -> None:
    """Test different filters.

    Filter_schema is also a fixture which is replaced by the filter_schema
    in the parametrize and added to the entry fixture.
    """
    count = 0

    for test in tests:
        count += test.expected_count

        hass.states.async_set(test.entity_id, STATE_ON)
        async_fire_time_changed(
            hass,
            utcnow() + timedelta(seconds=entry_managed.options[CONF_SEND_INTERVAL]),
        )
        await hass.async_block_till_done()
        assert (
            mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.call_count
            == count
        )
        mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.add.reset_mock()


async def test_Mailformed_event(
    hass,
    entry_managed,
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data,
) -> None:
    # pylint: disable=protected-access
    """Test listening to events from Hass. and getting an event with a newline in the state."""

    hass.states.async_set("sensor.test_sensor", "______\nMicrosof}")

    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=entry_managed.options[CONF_SEND_INTERVAL])
    )

    await hass.async_block_till_done()
    mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data.add.assert_not_called()
