"""Tests for the update coordinator."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import pytest

from homeassistant.helpers import update_coordinator
from homeassistant.util.dt import utcnow

from tests.async_mock import AsyncMock, Mock, patch
from tests.common import async_fire_time_changed

LOGGER = logging.getLogger(__name__)


@pytest.fixture
def crd(hass):
    """Coordinator mock."""
    calls = 0

    async def refresh():
        nonlocal calls
        calls += 1
        return calls

    crd = update_coordinator.DataUpdateCoordinator(
        hass,
        LOGGER,
        name="test",
        update_method=refresh,
        update_interval=timedelta(seconds=10),
    )
    return crd


async def test_async_refresh(crd):
    """Test async_refresh for update coordinator."""
    utc_time = utcnow()
    with patch("homeassistant.helpers.update_coordinator.utcnow") as mock_utc:
        mock_utc.return_value = utc_time
        assert crd.data is None
        await crd.async_refresh()
        assert crd.data == 1
        assert crd.last_update_success is True
        assert crd.last_update_success_time == utc_time
        # Make sure we didn't schedule a refresh because we have 0 listeners
        assert crd._unsub_refresh is None

    updates = []

    def update_callback():
        updates.append(crd.data)

    unsub = crd.async_add_listener(update_callback)
    await crd.async_refresh()
    assert updates == [2]
    assert crd._unsub_refresh is not None

    # Test unsubscribing through function
    unsub()
    await crd.async_refresh()
    assert updates == [2]

    # Test unsubscribing through method
    crd.async_add_listener(update_callback)
    crd.async_remove_listener(update_callback)
    await crd.async_refresh()
    assert updates == [2]


async def test_request_refresh(crd):
    """Test request refresh for update coordinator."""
    assert crd.data is None
    await crd.async_request_refresh()
    assert crd.data == 1
    assert crd.last_update_success is True

    # Second time we hit the debonuce
    await crd.async_request_refresh()
    assert crd.data == 1
    assert crd.last_update_success is True


@pytest.mark.parametrize(
    "err_msg",
    [
        (asyncio.TimeoutError, "Timeout fetching test data"),
        (aiohttp.ClientError, "Error requesting test data"),
        (update_coordinator.UpdateFailed, "Error fetching test data"),
    ],
)
async def test_refresh_known_errors(err_msg, crd, caplog):
    """Test raising known errors."""
    crd.update_method = AsyncMock(side_effect=err_msg[0])

    await crd.async_refresh()

    assert crd.data is None
    assert crd.last_update_success is False
    assert err_msg[1] in caplog.text


async def test_refresh_fail_unknown(crd, caplog):
    """Test raising unknown error."""
    await crd.async_refresh()

    crd.update_method = AsyncMock(side_effect=ValueError)

    await crd.async_refresh()

    assert crd.data == 1  # value from previous fetch
    assert crd.last_update_success is False
    assert "Unexpected error fetching test data" in caplog.text


async def test_refresh_no_update_method(crd):
    """Test raising error is no update method is provided."""
    await crd.async_refresh()

    crd.update_method = None

    with pytest.raises(NotImplementedError):
        await crd.async_refresh()


async def test_update_interval(hass, crd):
    """Test update interval works."""
    # Test we don't update without subscriber
    utc_time = utcnow()
    with patch("homeassistant.helpers.update_coordinator.utcnow") as mock_utc:
        mock_utc.return_value = utc_time + crd.update_interval
        async_fire_time_changed(hass, mock_utc.return_value)
        await hass.async_block_till_done()
        assert crd.data is None
        assert crd.last_update_success_time is None

        # Add subscriber
        update_callback = Mock()
        crd.async_add_listener(update_callback)

        # Test twice we update with subscriber
        mock_utc.return_value += crd.update_interval
        async_fire_time_changed(hass, mock_utc.return_value)
        await hass.async_block_till_done()
        assert crd.data == 1
        assert crd.last_update_success_time == mock_utc.return_value

        mock_utc.return_value += crd.update_interval
        async_fire_time_changed(hass, mock_utc.return_value)
        await hass.async_block_till_done()
        assert crd.data == 2
        assert crd.last_update_success_time == mock_utc.return_value
        last_success_time = mock_utc.return_value

        # Test removing listener
        crd.async_remove_listener(update_callback)

        mock_utc.return_value += crd.update_interval
        async_fire_time_changed(hass, mock_utc.return_value)
        await hass.async_block_till_done()

        # Test we stop updating after we lose last subscriber
        assert crd.data == 2
        assert crd.last_update_success_time == last_success_time


async def test_failed_update_interval(crd, hass):
    """Test failed update interval."""
    utc_time = utcnow()
    with patch("homeassistant.core.dt_util.utcnow") as mock_utcnow:
        mock_utcnow.return_value = utc_time
        old_update_method = crd.update_method
        crd.update_method = AsyncMock(side_effect=asyncio.TimeoutError)
        crd.failed_update_interval = timedelta(seconds=5)

        def update_callback():
            pass

        crd.async_add_listener(update_callback)

        await crd.async_refresh()
        await hass.async_block_till_done()

        assert crd.data is None
        assert crd.last_update_success is False

        crd.update_method = old_update_method
        mock_utcnow.return_value += timedelta(seconds=5)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert crd.data == 1
        assert crd.last_update_success is True


async def test_refresh_recover(crd, caplog):
    """Test recovery of freshing data."""
    crd.last_update_success = False

    await crd.async_refresh()

    assert crd.last_update_success is True
    assert "Fetching test data recovered" in caplog.text
