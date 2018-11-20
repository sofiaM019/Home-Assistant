"""The tests for the geojson platform."""
from unittest.mock import patch, MagicMock, call

import homeassistant
from homeassistant.components import geo_location
from homeassistant.components.geo_location import ATTR_SOURCE
from homeassistant.components.geo_location.geo_json_events import \
    SCAN_INTERVAL, ATTR_EXTERNAL_ID
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_START, \
    CONF_RADIUS, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_FRIENDLY_NAME, \
    ATTR_UNIT_OF_MEASUREMENT, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.setup import async_setup_component
from tests.common import assert_setup_component, async_fire_time_changed
import homeassistant.util.dt as dt_util

URL = 'http://geo.json.local/geo_json_events.json'
CONFIG = {
    geo_location.DOMAIN: [
        {
            'platform': 'geo_json_events',
            CONF_URL: URL,
            CONF_RADIUS: 200
        }
    ]
}

CONFIG_WITH_CUSTOM_LOCATION = {
    geo_location.DOMAIN: [
        {
            'platform': 'geo_json_events',
            CONF_URL: URL,
            CONF_RADIUS: 200,
            CONF_LATITUDE: 15.1,
            CONF_LONGITUDE: 25.2
        }
    ]
}


def _generate_mock_feed_entry(external_id, title, distance_to_home,
                              coordinates):
    """Construct a mock feed entry for testing purposes."""
    feed_entry = MagicMock()
    feed_entry.external_id = external_id
    feed_entry.title = title
    feed_entry.distance_to_home = distance_to_home
    feed_entry.coordinates = coordinates
    return feed_entry


async def test_setup(hass):
    """Test the general setup of the platform."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        '1234', 'Title 1', 15.5, (-31.0, 150.0))
    mock_entry_2 = _generate_mock_feed_entry(
        '2345', 'Title 2', 20.5, (-31.1, 150.1))
    mock_entry_3 = _generate_mock_feed_entry(
        '3456', 'Title 3', 25.5, (-31.2, 150.2))
    mock_entry_4 = _generate_mock_feed_entry(
        '4567', 'Title 4', 12.5, (-31.3, 150.3))

    # Patching 'utcnow' to gain more control over the timed update.
    utcnow = dt_util.utcnow()
    with patch('homeassistant.util.dt.utcnow', return_value=utcnow), \
            patch('geojson_client.generic_feed.GenericFeed') as mock_feed:
        mock_feed.return_value.update.return_value = 'OK', [mock_entry_1,
                                                            mock_entry_2,
                                                            mock_entry_3]
        with assert_setup_component(1, geo_location.DOMAIN):
            assert await async_setup_component(
                hass, geo_location.DOMAIN, CONFIG)
            # Artificially trigger update.
            hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
            # Collect events.
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 3

            state = hass.states.get("geo_location.title_1")
            assert state is not None
            assert state.name == "Title 1"
            assert state.attributes == {
                ATTR_EXTERNAL_ID: "1234", ATTR_LATITUDE: -31.0,
                ATTR_LONGITUDE: 150.0, ATTR_FRIENDLY_NAME: "Title 1",
                ATTR_UNIT_OF_MEASUREMENT: "km",
                ATTR_SOURCE: 'geo_json_events'}
            assert round(abs(float(state.state)-15.5), 7) == 0

            state = hass.states.get("geo_location.title_2")
            assert state is not None
            assert state.name == "Title 2"
            assert state.attributes == {
                ATTR_EXTERNAL_ID: "2345", ATTR_LATITUDE: -31.1,
                ATTR_LONGITUDE: 150.1, ATTR_FRIENDLY_NAME: "Title 2",
                ATTR_UNIT_OF_MEASUREMENT: "km",
                ATTR_SOURCE: 'geo_json_events'}
            assert round(abs(float(state.state)-20.5), 7) == 0

            state = hass.states.get("geo_location.title_3")
            assert state is not None
            assert state.name == "Title 3"
            assert state.attributes == {
                ATTR_EXTERNAL_ID: "3456", ATTR_LATITUDE: -31.2,
                ATTR_LONGITUDE: 150.2, ATTR_FRIENDLY_NAME: "Title 3",
                ATTR_UNIT_OF_MEASUREMENT: "km",
                ATTR_SOURCE: 'geo_json_events'}
            assert round(abs(float(state.state)-25.5), 7) == 0

            # Simulate an update - one existing, one new entry,
            # one outdated entry
            mock_feed.return_value.update.return_value = 'OK', [
                mock_entry_1, mock_entry_4, mock_entry_3]
            async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 3

            # Simulate an update - empty data, but successful update,
            # so no changes to entities.
            mock_feed.return_value.update.return_value = 'OK_NO_DATA', None
            async_fire_time_changed(hass, utcnow + 2 * SCAN_INTERVAL)
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 3

            # Simulate an update - empty data, removes all entities
            mock_feed.return_value.update.return_value = 'ERROR', None
            async_fire_time_changed(hass, utcnow + 3 * SCAN_INTERVAL)
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 0


async def test_setup_with_custom_location(hass):
    """Test the setup with a custom location."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        '1234', 'Title 1', 2000.5, (-31.1, 150.1))

    with patch('geojson_client.generic_feed.GenericFeed') as mock_feed:
        mock_feed.return_value.update.return_value = 'OK', [mock_entry_1]

        with assert_setup_component(1, geo_location.DOMAIN):
            assert await async_setup_component(
                hass, geo_location.DOMAIN, CONFIG_WITH_CUSTOM_LOCATION)

            # Artificially trigger update.
            hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
            # Collect events.
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 1

            assert mock_feed.call_args == call(
                (15.1, 25.2), URL, filter_radius=200.0)


async def test_setup_race_condition(hass):
    """Test a particular race condition experienced."""
    # 1. Feed returns 1 entry -> Feed manager creates 1 entity.
    # 2. Feed returns error -> Feed manager removes 1 entity.
    #    However, this stayed on and kept listening for dispatcher signals.
    # 3. Feed returns 1 entry -> Feed manager creates 1 entity.
    # 4. Feed returns 1 entry -> Feed manager updates 1 entity.
    #    Internally, the previous entity is updating itself, too.
    # 5. Feed returns error -> Feed manager removes 1 entity.
    #    There are now 2 entities trying to remove themselves from HA, but
    #    the second attempt fails of course.

    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        '1234', 'Title 1', 15.5, (-31.0, 150.0))

    # Patching 'utcnow' to gain more control over the timed update.
    utcnow = dt_util.utcnow()
    with patch('homeassistant.util.dt.utcnow', return_value=utcnow), \
            patch('geojson_client.generic_feed.GenericFeed') as mock_feed:
        with assert_setup_component(1, geo_location.DOMAIN):
            assert await async_setup_component(
                hass, geo_location.DOMAIN, CONFIG)

            # This gives us the ability to assert the '_delete_callback'
            # has been called while still executing it.
            original_delete_callback = homeassistant.components\
                .geo_location.geo_json_events.GeoJsonLocationEvent\
                ._delete_callback

            def mock_delete_callback(entity):
                original_delete_callback(entity)

            with patch('homeassistant.components.geo_location'
                       '.geo_json_events.GeoJsonLocationEvent'
                       '._delete_callback',
                       side_effect=mock_delete_callback,
                       autospec=True) as mocked_delete_callback:

                mock_feed.return_value.update.return_value = 'OK', [
                    mock_entry_1]

                # Artificially trigger update.
                hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
                # Collect events.
                await hass.async_block_till_done()

                all_states = hass.states.async_all()
                assert len(all_states) == 1

                # Simulate an update - empty data, removes all entities
                mock_feed.return_value.update.return_value = 'ERROR', None
                async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
                await hass.async_block_till_done()

                assert mocked_delete_callback.call_count == 1
                all_states = hass.states.async_all()
                assert len(all_states) == 0

                # Simulate an update - 1 entry
                mock_feed.return_value.update.return_value = 'OK', [
                    mock_entry_1]
                async_fire_time_changed(hass, utcnow + 2 * SCAN_INTERVAL)
                await hass.async_block_till_done()

                all_states = hass.states.async_all()
                assert len(all_states) == 1

                # Simulate an update - 1 entry
                mock_feed.return_value.update.return_value = 'OK', [
                    mock_entry_1]
                async_fire_time_changed(hass, utcnow + 3 * SCAN_INTERVAL)
                await hass.async_block_till_done()

                all_states = hass.states.async_all()
                assert len(all_states) == 1

                # Reset mocked method for the next test.
                mocked_delete_callback.reset_mock()

                # Simulate an update - empty data, removes all entities
                mock_feed.return_value.update.return_value = 'ERROR', None
                async_fire_time_changed(hass, utcnow + 4 * SCAN_INTERVAL)
                await hass.async_block_till_done()

                assert mocked_delete_callback.call_count == 1
                all_states = hass.states.async_all()
                assert len(all_states) == 0
