"""The tests for the Recorder component."""
# pylint: disable=protected-access
import asyncio
import json
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch, call, MagicMock

import pytest
from sqlalchemy import create_engine

from homeassistant.core import callback
from homeassistant.bootstrap import async_setup_component
from homeassistant.const import MATCH_ALL
from homeassistant.components import recorder
from tests.common import get_test_home_assistant, init_recorder_component
from tests.components.recorder import models_original


class BaseTestRecorder(unittest.TestCase):
    """Base class for common recorder tests."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        init_recorder_component(self.hass)
        self.hass.start()
        recorder.get_instance().block_till_done()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()
        with self.assertRaises(RuntimeError):
            recorder.get_instance()

    def _add_test_states(self):
        """Add multiple states to the db for testing."""
        now = datetime.now()
        five_days_ago = now - timedelta(days=5)
        attributes = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.block_till_done()
        recorder._INSTANCE.block_till_done()

        with recorder.session_scope() as session:
            for event_id in range(5):
                if event_id < 3:
                    timestamp = five_days_ago
                    state = 'purgeme'
                else:
                    timestamp = now
                    state = 'dontpurgeme'

                session.add(recorder.get_model('States')(
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
        recorder._INSTANCE.block_till_done()

        with recorder.session_scope() as session:
            for event_id in range(5):
                if event_id < 2:
                    timestamp = five_days_ago
                    event_type = 'EVENT_TEST_PURGE'
                else:
                    timestamp = now
                    event_type = 'EVENT_TEST'

                session.add(recorder.get_model('Events')(
                    event_type=event_type,
                    event_data=json.dumps(event_data),
                    origin='LOCAL',
                    created=timestamp,
                    time_fired=timestamp,
                ))


class TestRecorder(BaseTestRecorder):
    """Test the recorder module."""

    def test_saving_state(self):
        """Test saving and restoring a state."""
        entity_id = 'test.recorder'
        state = 'restoring_from_db'
        attributes = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.states.set(entity_id, state, attributes)

        self.hass.block_till_done()
        recorder._INSTANCE.block_till_done()

        db_states = recorder.query('States')
        states = recorder.execute(db_states)

        assert db_states[0].event_id is not None

        self.assertEqual(1, len(states))
        self.assertEqual(self.hass.states.get(entity_id), states[0])

    def test_saving_event(self):
        """Test saving and restoring an event."""
        event_type = 'EVENT_TEST'
        event_data = {'test_attr': 5, 'test_attr_10': 'nice'}

        events = []

        @callback
        def event_listener(event):
            """Record events from eventbus."""
            if event.event_type == event_type:
                events.append(event)

        self.hass.bus.listen(MATCH_ALL, event_listener)

        self.hass.bus.fire(event_type, event_data)

        self.hass.block_till_done()
        recorder._INSTANCE.block_till_done()

        db_events = recorder.execute(
            recorder.query('Events').filter_by(
                event_type=event_type))

        assert len(events) == 1
        assert len(db_events) == 1

        event = events[0]
        db_event = db_events[0]

        assert event.event_type == db_event.event_type
        assert event.data == db_event.data
        assert event.origin == db_event.origin

        # Recorder uses SQLite and stores datetimes as integer unix timestamps
        assert event.time_fired.replace(microsecond=0) == \
            db_event.time_fired.replace(microsecond=0)

    def test_purge_old_states(self):
        """Test deleting old states."""
        self._add_test_states()
        # make sure we start with 5 states
        states = recorder.query('States')
        self.assertEqual(states.count(), 5)

        # run purge_old_data()
        recorder._INSTANCE.purge_days = 4
        recorder._INSTANCE._purge_old_data()

        # we should only have 2 states left after purging
        self.assertEqual(states.count(), 2)

    def test_purge_old_events(self):
        """Test deleting old events."""
        self._add_test_events()
        events = recorder.query('Events').filter(
            recorder.get_model('Events').event_type.like("EVENT_TEST%"))
        self.assertEqual(events.count(), 5)

        # run purge_old_data()
        recorder._INSTANCE.purge_days = 4
        recorder._INSTANCE._purge_old_data()

        # now we should only have 3 events left
        self.assertEqual(events.count(), 3)

    def test_schema_no_recheck(self):
        """Test that schema is not double-checked when up-to-date."""
        with patch.object(recorder._INSTANCE, '_apply_update') as update, \
                patch.object(recorder._INSTANCE, '_inspect_schema_version') \
                as inspect:
            recorder._INSTANCE._migrate_schema()
            self.assertEqual(update.call_count, 0)
            self.assertEqual(inspect.call_count, 0)

    def test_invalid_update(self):
        """Test that an invalid new version raises an exception."""
        with self.assertRaises(ValueError):
            recorder._INSTANCE._apply_update(-1)


def create_engine_test(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    engine = create_engine(*args, **kwargs)
    models_original.Base.metadata.create_all(engine)
    return engine


class TestMigrateRecorder(BaseTestRecorder):
    """Test recorder class that starts with an original schema db."""

    @patch('sqlalchemy.create_engine', new=create_engine_test)
    @patch('homeassistant.components.recorder.Recorder._migrate_schema')
    def setUp(self, migrate):  # pylint: disable=invalid-name,arguments-differ
        """Setup things to be run when tests are started.

        create_engine is patched to create a db that starts with the old
        schema.

        _migrate_schema is mocked to ensure it isn't run, so we can test it
        below.
        """
        super().setUp()

    def test_schema_update_calls(self):  # pylint: disable=no-self-use
        """Test that schema migrations occurr in correct order."""
        with patch.object(recorder._INSTANCE, '_apply_update') as update:
            recorder._INSTANCE._migrate_schema()
            update.assert_has_calls([call(version+1) for version in range(
                0, recorder.models.SCHEMA_VERSION)])

    def test_schema_migrate(self):  # pylint: disable=no-self-use
        """Test the full schema migration logic.

        We're just testing that the logic can execute successfully here without
        throwing exceptions. Maintaining a set of assertions based on schema
        inspection could quickly become quite cumbersome.
        """
        recorder._INSTANCE._migrate_schema()


@pytest.fixture
def hass_recorder():
    """HASS fixture with in-memory recorder."""
    hass = get_test_home_assistant()

    def setup_recorder(config=None):
        """Setup with params."""
        init_recorder_component(hass, config)
        hass.start()
        hass.block_till_done()
        recorder.get_instance().block_till_done()
        return hass

    yield setup_recorder
    hass.stop()


def _add_entities(hass, entity_ids):
    """Add entities."""
    attributes = {'test_attr': 5, 'test_attr_10': 'nice'}
    for idx, entity_id in enumerate(entity_ids):
        hass.states.set(entity_id, 'state{}'.format(idx), attributes)
        hass.block_till_done()
    recorder._INSTANCE.block_till_done()
    db_states = recorder.query('States')
    states = recorder.execute(db_states)
    assert db_states[0].event_id is not None
    return states


# pylint: disable=redefined-outer-name,invalid-name
def test_saving_state_include_domains(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({'include': {'domains': 'test2'}})
    states = _add_entities(hass, ['test.recorder', 'test2.recorder'])
    assert len(states) == 1
    assert hass.states.get('test2.recorder') == states[0]


def test_saving_state_incl_entities(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({'include': {'entities': 'test2.recorder'}})
    states = _add_entities(hass, ['test.recorder', 'test2.recorder'])
    assert len(states) == 1
    assert hass.states.get('test2.recorder') == states[0]


def test_saving_state_exclude_domains(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({'exclude': {'domains': 'test'}})
    states = _add_entities(hass, ['test.recorder', 'test2.recorder'])
    assert len(states) == 1
    assert hass.states.get('test2.recorder') == states[0]


def test_saving_state_exclude_entities(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({'exclude': {'entities': 'test.recorder'}})
    states = _add_entities(hass, ['test.recorder', 'test2.recorder'])
    assert len(states) == 1
    assert hass.states.get('test2.recorder') == states[0]


def test_saving_state_exclude_domain_include_entity(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({
        'include': {'entities': 'test.recorder'},
        'exclude': {'domains': 'test'}})
    states = _add_entities(hass, ['test.recorder', 'test2.recorder'])
    assert len(states) == 2


def test_saving_state_include_domain_exclude_entity(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({
        'exclude': {'entities': 'test.recorder'},
        'include': {'domains': 'test'}})
    states = _add_entities(hass, ['test.recorder', 'test2.recorder',
                                  'test.ok'])
    assert len(states) == 1
    assert hass.states.get('test.ok') == states[0]
    assert hass.states.get('test.ok').state == 'state2'


def test_recorder_errors_exceptions(hass_recorder): \
        # pylint: disable=redefined-outer-name
    """Test session_scope and get_model errors."""
    # Model cannot be resolved
    assert recorder.get_model('dont-exist') is None

    # Verify the instance fails before setup
    with pytest.raises(RuntimeError):
        recorder.get_instance()

    # Setup the recorder
    hass_recorder()

    recorder.get_instance()

    # Verify session scope raises (and prints) an exception
    with patch('homeassistant.components.recorder._LOGGER.error') as e_mock, \
            pytest.raises(Exception) as err:
        with recorder.session_scope() as session:
            session.execute('select * from notthere')
    assert e_mock.call_count == 1
    assert recorder.ERROR_QUERY[:-4] in e_mock.call_args[0][0]
    assert 'no such table' in str(err.value)


def test_recorder_bad_commit(hass_recorder):
    """Bad _commit should retry 3 times."""
    hass_recorder()

    def work(session):
        """Bad work."""
        session.execute('select * from notthere')

    with patch('homeassistant.components.recorder.time.sleep') as e_mock, \
            recorder.session_scope() as session:
        res = recorder._INSTANCE._commit(session, work)
    assert res is False
    assert e_mock.call_count == 3


def test_recorder_bad_execute(hass_recorder):
    """Bad execute, retry 3 times."""
    hass_recorder()

    def to_native():
        """Rasie exception."""
        from sqlalchemy.exc import SQLAlchemyError
        raise SQLAlchemyError()

    mck1 = MagicMock()
    mck1.to_native = to_native

    with patch('homeassistant.components.recorder.time.sleep') as e_mock:
        res = recorder.execute((mck1,))
    assert res == []
    assert e_mock.call_count == 3


@asyncio.coroutine
def test_recorder_fails_setup_when_connection_fails(hass):
    """Test recorder fails to setup when SQLAlchemy fails."""
    from sqlalchemy.exc import SQLAlchemyError
    with patch('homeassistant.components.recorder.Recorder.initialize',
               side_effect=SQLAlchemyError('Bad auth, yo')):
        result = yield from async_setup_component(hass, 'recorder', {})
        assert not result
