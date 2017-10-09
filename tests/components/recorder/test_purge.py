"""Test data purging."""
import json
from datetime import datetime, timedelta
from time import sleep
import unittest
from unittest.mock import patch

import homeassistant.util.dt as dt_util
from homeassistant.components import recorder
from homeassistant.components.recorder import PurgeTask
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.purge import purge_old_data
from homeassistant.components.recorder.models import States, Events, PurgeRun
from homeassistant.components.recorder.util import session_scope
from tests.common import get_test_home_assistant, init_recorder_component


class TestRecorderPurge(unittest.TestCase):
    """Base class for common recorder tests."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        config = {'purge_keep_days': 4, 'purge_interval': 2}
        self.hass = get_test_home_assistant()
        init_recorder_component(self.hass, config)
        self.hass.start()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def _add_test_states(self):
        """Add multiple states to the db for testing."""
        now = datetime.now()
        five_days_ago = now - timedelta(days=5)
        attributes = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.block_till_done()
        self.hass.data[DATA_INSTANCE].block_till_done()

        with recorder.session_scope(hass=self.hass) as session:
            for event_id in range(5):
                if event_id < 3:
                    timestamp = five_days_ago
                    state = 'purgeme'
                else:
                    timestamp = now
                    state = 'dontpurgeme'

                session.add(States(
                    entity_id='test.recorder2',
                    domain='sensor',
                    state=state,
                    attributes=json.dumps(attributes),
                    last_changed=timestamp,
                    last_updated=timestamp,
                    created=timestamp,
                    event_id=event_id + 1000
                ))

    def _add_test_events(self):
        """Add a few events for testing."""
        now = datetime.now()
        five_days_ago = now - timedelta(days=5)
        event_data = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.block_till_done()
        self.hass.data[DATA_INSTANCE].block_till_done()

        with recorder.session_scope(hass=self.hass) as session:
            for event_id in range(5):
                if event_id < 2:
                    timestamp = five_days_ago
                    event_type = 'EVENT_TEST_PURGE'
                else:
                    timestamp = now
                    event_type = 'EVENT_TEST'

                session.add(Events(
                    event_type=event_type,
                    event_data=json.dumps(event_data),
                    origin='LOCAL',
                    created=timestamp,
                    time_fired=timestamp,
                ))

    def test_purge_old_states(self):
        """Test deleting old states."""
        self._add_test_states()
        # make sure we start with 5 states
        with session_scope(hass=self.hass) as session:
            states = session.query(States)
            self.assertEqual(states.count(), 5)

            # run purge_old_data()
            purge_old_data(self.hass.data[DATA_INSTANCE], 4)

            # we should only have 2 states left after purging
            self.assertEqual(states.count(), 2)

    def test_purge_old_events(self):
        """Test deleting old events."""
        self._add_test_events()

        with session_scope(hass=self.hass) as session:
            events = session.query(Events).filter(
                Events.event_type.like("EVENT_TEST%"))
            self.assertEqual(events.count(), 5)

            # run purge_old_data()
            purge_old_data(self.hass.data[DATA_INSTANCE], 4)

            # now we should only have 3 events left
            self.assertEqual(events.count(), 3)

    def test_purge_method(self):
        """Test purge method."""
        service_data = {'keep_days': 4}
        self._add_test_states()
        self._add_test_events()

        # make sure we start with 5 states
        with session_scope(hass=self.hass) as session:
            states = session.query(States)
            self.assertEqual(states.count(), 5)

            events = session.query(Events).filter(
                Events.event_type.like("EVENT_TEST%"))
            self.assertEqual(events.count(), 5)

            self.hass.data[DATA_INSTANCE].block_till_done()

            # run purge method - no service data, should not work
            self.hass.services.call('recorder', 'purge')
            self.hass.async_block_till_done()

            # Small wait for recorder thread
            sleep(0.1)

            # we should only have 2 states left after purging
            self.assertEqual(states.count(), 5)

            # now we should only have 3 events left
            self.assertEqual(events.count(), 5)

            # run purge method - correct service data
            self.hass.services.call('recorder', 'purge',
                                    service_data=service_data)
            self.hass.async_block_till_done()

            # Small wait for recorder thread
            sleep(0.1)

            # we should only have 2 states left after purging
            self.assertEqual(states.count(), 2)

            # now we should only have 3 events left
            self.assertEqual(events.count(), 3)


class TestPurgeRun(unittest.TestCase):
    """Base class for purge run tests."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_purge_not_initialised(self):
        """Purge timestamp is None if purging never initialised."""
        config = {}
        init_recorder_component(self.hass, config)
        with session_scope(hass=self.hass) as session:
            run = session.query(PurgeRun).one_or_none()
            self.assertIsNone(run)

    def test_purge_initialised(self):
        """Purge timestamp defaults to utcnow() when first initialised."""
        now = dt_util.parse_datetime("2017-10-17 17:17:17.171717+0000")
        with patch('homeassistant.components.recorder.dt_util.utcnow') \
                as now_mock:
            now_mock.return_value = now
            config = {'purge_keep_days': 4, 'purge_interval': 2}
            init_recorder_component(self.hass, config)

        with session_scope(hass=self.hass) as session:
            run = session.query(PurgeRun).one_or_none()
            self.assertIsNotNone(run)
            self.assertIsInstance(run.last, datetime)
            self.assertEqual(dt_util.UTC.localize(run.last), now)

    @patch('homeassistant.components.recorder.purge.query_last_purge_time')
    @patch('homeassistant.components.recorder.async_track_point_in_time')
    def test_purge_skipped(self, track_mock, query_mock):
        """Purge schedule maintained if purge skipped (e.g. HA restarts)."""
        now = dt_util.utcnow()
        last_purge = now - timedelta(days=7)
        next_purge = now + timedelta(minutes=30)

        # Mock the last purge as seven days ago
        query_mock.return_value = last_purge
        config = {'purge_keep_days': 4, 'purge_interval': 2}
        init_recorder_component(self.hass, config)

        # Expect next purge to be scheduled for 30 minutes after restart
        self.assertEqual(track_mock.call_count, 1)
        self.assertAlmostEqual(track_mock.call_args_list[0][0][2],
                               next_purge, delta=timedelta(seconds=1))

    def test_purge_updated(self):
        """Purge timestamp is updated after a scheduled purge."""
        config = {'purge_keep_days': 4, 'purge_interval': 2}
        init_recorder_component(self.hass, config)
        self.hass.start()

        # Trigger a purge and record utcnow() as timestamp
        now = dt_util.utcnow()
        self.hass.data[DATA_INSTANCE].queue.put(
            PurgeTask(config['purge_keep_days'], now))

        self.hass.block_till_done()
        self.hass.data[DATA_INSTANCE].block_till_done()

        # Confirm that last purge timestamp is utcnow()
        with session_scope(hass=self.hass) as session:
            run = session.query(PurgeRun).one_or_none()
            self.assertIsNotNone(run)
            self.assertEqual(dt_util.UTC.localize(run.last), now)
