"""Tests for the Withings component."""
import time
import nokia
from asynctest import patch, MagicMock
from tests.common import get_test_home_assistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.withings.common import (
    WithingsDataManager
)
from homeassistant.components.withings import (
    const
)
from homeassistant.components.withings.sensor import (
    WITHINGS_MEASUREMENTS_MAP,
    WithingsHealthSensor,
    async_setup_entry
)


async def test_async_setup_entry(hass):
    """Test setup of config entry."""
    import nokia
    nokia_api_patch = patch('nokia.NokiaApi')
    withings_data_manager_patch = patch(
        'homeassistant.components.withings.common.WithingsDataManager'
    )
    withings_health_sensor_patch = patch(
        'homeassistant.components.withings.sensor.WithingsHealthSensor'
    )

    with nokia_api_patch as nokia_api_mock, \
            withings_data_manager_patch as data_manager_mock, \
            withings_health_sensor_patch as health_sensor_mock:

        async def async_refresh_token():
            pass

        nokia_api_instance = MagicMock(spec=nokia.NokiaApi)
        nokia_api_instance.get_user = MagicMock()
        nokia_api_instance.credentials = MagicMock(spec=nokia.NokiaCredentials)
        nokia_api_instance.credentials.token_expiry = 99999999999999
        nokia_api_instance.request = MagicMock()

        data_manager_instance = MagicMock(spec=WithingsDataManager)
        data_manager_instance.async_refresh_token = async_refresh_token

        nokia_api_mock.return_value = nokia_api_instance
        data_manager_mock.return_value = data_manager_instance
        health_sensor_mock.return_value = MagicMock(spec=WithingsHealthSensor)

        async_add_entities = MagicMock()
        config_entry = ConfigEntry(
            'version',
            'domain',
            'title',
            {
                const.PROFILE: 'Person 1',
                const.CREDENTIALS: {
                    'access_token': 'my_access_token',
                    'token_expiry': 'my_token_expiry',
                    'token_type': 'my_token_type',
                    'refresh_token': 'my_refresh_token',
                    'user_id': 'my_user_id',
                    'client_id': 'my_client_id',
                    'consumer_secret': 'my_consumer_secret'
                },
            },
            'source',
            'connection_class'
        )

        result = await async_setup_entry(
            hass,
            config_entry,
            async_add_entities
        )

        assert result

        nokia_api_instance.request.assert_called_with('user', 'getdevice', version='v2')


class TestWithingsHealthSensor:
    """Tests all the health sensors."""

    def setup_method(self):
        """Set up the test."""
        self.hass = get_test_home_assistant()

        self.api = nokia.NokiaApi.__new__(nokia.NokiaApi)
        self.api.get_credentials = MagicMock(
            return_value=nokia.NokiaCredentials(
                user_id='USER_ID'
            )
        )
        self.api.get_measures = MagicMock()
        self.api.get_sleep = MagicMock()
        self.api.get_sleep_summary = MagicMock()

        self.recreate_data_manager()

    def teardown_method(self):
        """Tear down the test."""
        self.hass.stop()

    def recreate_data_manager(self):
        """Recreate data manager to get arround the @Trottle decorators."""
        self.data_manager = WithingsDataManager(
            'person_1',
            self.api
        )

    def test_properties(self):
        """Test method."""
        sensor = WithingsHealthSensor(
            self.data_manager,
            WITHINGS_MEASUREMENTS_MAP[const.MEAS_WEIGHT_KG]
        )

        assert sensor.name == 'Withings weight_kg person_1'
        assert sensor.unique_id == 'withings_person_1_USER_ID_weight_kg'
        assert sensor.state is None
        assert sensor.unit_of_measurement == 'kg'
        assert sensor.icon == 'mdi:weight-kilogram'

    async def test_async_update(self):
        """Test method."""
        self.api.get_measures.return_value = nokia.NokiaMeasures({
            'updatetime': '',
            'timezone': '',
            'measuregrps': [
                # Un-ambiguous groups.
                new_measure_group(
                    1, 0, time.time(), time.time(), 1, 'DEV_ID', False, 0, [
                        new_measure(const.MEASURE_TYPE_WEIGHT, 70, 0),
                        new_measure(const.MEASURE_TYPE_FAT_MASS, 5, 0),
                        new_measure(
                            const.MEASURE_TYPE_FAT_MASS_FREE, 60, 0
                        ),
                        new_measure(const.MEASURE_TYPE_MUSCLE_MASS, 50, 0),
                        new_measure(const.MEASURE_TYPE_BONE_MASS, 10, 0),
                        new_measure(const.MEASURE_TYPE_HEIGHT, 2, 0),
                        new_measure(const.MEASURE_TYPE_TEMP, 40, 0),
                        new_measure(const.MEASURE_TYPE_BODY_TEMP, 35, 0),
                        new_measure(const.MEASURE_TYPE_SKIN_TEMP, 20, 0),
                        new_measure(const.MEASURE_TYPE_FAT_RATIO, 70, -3),
                        new_measure(const.MEASURE_TYPE_DIASTOLIC_BP, 70, 0),
                        new_measure(const.MEASURE_TYPE_SYSTOLIC_BP, 100, 0),
                        new_measure(const.MEASURE_TYPE_HEART_PULSE, 60, 0),
                        new_measure(const.MEASURE_TYPE_SPO2, 95, -2),
                        new_measure(const.MEASURE_TYPE_HYDRATION, 95, -2),
                        new_measure(const.MEASURE_TYPE_PWV, 100, 0),
                    ]
                ),

                # Ambiguous groups (we ignore these)
                new_measure_group(
                    1, 1, time.time(), time.time(), 1, 'DEV_ID', False, 0, [
                        new_measure(const.MEASURE_TYPE_WEIGHT, 71, 0),
                        new_measure(const.MEASURE_TYPE_FAT_MASS, 4, 0),
                        new_measure(const.MEASURE_TYPE_MUSCLE_MASS, 51, 0),
                        new_measure(const.MEASURE_TYPE_BONE_MASS, 11, 0),
                        new_measure(const.MEASURE_TYPE_HEIGHT, 201, 0),
                        new_measure(const.MEASURE_TYPE_TEMP, 41, 0),
                        new_measure(const.MEASURE_TYPE_BODY_TEMP, 34, 0),
                        new_measure(const.MEASURE_TYPE_SKIN_TEMP, 21, 0),
                        new_measure(const.MEASURE_TYPE_FAT_RATIO, 71, -3),
                        new_measure(const.MEASURE_TYPE_DIASTOLIC_BP, 71, 0),
                        new_measure(const.MEASURE_TYPE_SYSTOLIC_BP, 101, 0),
                        new_measure(const.MEASURE_TYPE_HEART_PULSE, 61, 0),
                        new_measure(const.MEASURE_TYPE_SPO2, 98, -2),
                        new_measure(const.MEASURE_TYPE_HYDRATION, 96, -2),
                        new_measure(const.MEASURE_TYPE_PWV, 102, 0),
                    ]
                )
            ],
            'more': False,
            'offset': 0
        })

        await self.assert_sensor_equals(70, const.MEAS_WEIGHT_KG)
        await self.assert_sensor_equals(154.35, const.MEAS_WEIGHT_LB)
        await self.assert_sensor_equals(11.02, const.MEAS_WEIGHT_STONE)
        await self.assert_sensor_equals(5, const.MEAS_FAT_MASS_KG)
        await self.assert_sensor_equals(11.03, const.MEAS_FAT_MASS_LB)
        await self.assert_sensor_equals(60, const.MEAS_FAT_FREE_MASS_KG)
        await self.assert_sensor_equals(132.3, const.MEAS_FAT_FREE_MASS_LB)
        await self.assert_sensor_equals(50, const.MEAS_MUSCLE_MASS_KG)
        await self.assert_sensor_equals(110.25, const.MEAS_MUSCLE_MASS_LB)
        await self.assert_sensor_equals(10, const.MEAS_BONE_MASS_KG)
        await self.assert_sensor_equals(22.05, const.MEAS_BONE_MASS_LB)
        await self.assert_sensor_equals(2, const.MEAS_HEIGHT_M)
        await self.assert_sensor_equals(200, const.MEAS_HEIGHT_CM)
        await self.assert_sensor_equals(78.74, const.MEAS_HEIGHT_IN)
        await self.assert_sensor_equals('6\' 6"', const.MEAS_HEIGHT_IMP)
        await self.assert_sensor_equals(40, const.MEAS_TEMP_C)
        await self.assert_sensor_equals(104, const.MEAS_TEMP_F)
        await self.assert_sensor_equals(35, const.MEAS_BODY_TEMP_C)
        await self.assert_sensor_equals(95.0, const.MEAS_BODY_TEMP_F)
        await self.assert_sensor_equals(20, const.MEAS_SKIN_TEMP_C)
        await self.assert_sensor_equals(68.0, const.MEAS_SKIN_TEMP_F)
        await self.assert_sensor_equals(7.0, const.MEAS_FAT_RATIO_PCT)
        await self.assert_sensor_equals(70, const.MEAS_DIASTOLIC_MMHG)
        await self.assert_sensor_equals(100, const.MEAS_SYSTOLIC_MMGH)
        await self.assert_sensor_equals(60, const.MEAS_HEART_PULSE_BPM)
        await self.assert_sensor_equals(95.0, const.MEAS_SPO2_PCT)
        await self.assert_sensor_equals(0.95, const.MEAS_HYDRATION)
        await self.assert_sensor_equals(100, const.MEAS_PWV)

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_AWAKE
                ),
                new_sleep_data_serie(
                    '2019-02-01 02:00:00',
                    '2019-02-01 02:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_DEEP
                ),
                new_sleep_data_serie(
                    '2019-02-01 01:00:00',
                    '2019-02-01 01:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_REM
                ),
            ]
        ))
        await self.assert_sensor_equals(
            const.STATE_DEEP,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_AWAKE
                ),
            ]
        ))
        await self.assert_sensor_equals(
            const.STATE_AWAKE,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_LIGHT
                ),
            ]
        ))
        await self.assert_sensor_equals(
            const.STATE_LIGHT,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_DEEP
                ),
            ]
        ))
        await self.assert_sensor_equals(
            const.STATE_DEEP,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_REM
                ),
            ]
        ))
        await self.assert_sensor_equals(
            const.STATE_REM,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = None
        await self.assert_sensor_equals(
            const.STATE_UNKNOWN,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(
            new_sleep_data('aa', [])
        )
        await self.assert_sensor_equals(
            const.STATE_UNKNOWN,
            const.MEAS_SLEEP_STATE
        )

        self.api.get_sleep_summary.return_value = nokia.NokiaSleepSummary({
            'series': [
                new_sleep_summary(
                    'UTC',
                    32,
                    '2019-02-01',
                    '2019-02-02',
                    '2019-02-02',
                    '12345',
                    new_sleep_summary_detail(
                        110,
                        210,
                        310,
                        410,
                        510,
                        610,
                        710,
                        810,
                        910,
                        1010,
                        1110,
                        1210,
                        1310
                    ),
                ),
                new_sleep_summary(
                    'UTC',
                    32,
                    '2019-02-01',
                    '2019-02-02',
                    '2019-02-02',
                    '12345',
                    new_sleep_summary_detail(
                        210,
                        310,
                        410,
                        510,
                        610,
                        710,
                        810,
                        910,
                        1010,
                        1110,
                        1210,
                        1310,
                        1410
                    ),
                )
            ]
        })

        await self.assert_sensor_equals(
            2.7, const.MEAS_SLEEP_WAKEUP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            4.3, const.MEAS_SLEEP_LIGHT_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            6.0, const.MEAS_SLEEP_DEEP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            7.7, const.MEAS_SLEEP_REM_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            160.0,
            const.MEAS_SLEEP_WAKEUP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            260.0,
            const.MEAS_SLEEP_LIGHT_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            360,
            const.MEAS_SLEEP_DEEP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            460.0,
            const.MEAS_SLEEP_REM_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            560.0,
            const.MEAS_SLEEP_WAKEUP_COUNT
        )
        await self.assert_sensor_equals(
            11.0,
            const.MEAS_SLEEP_TOSLEEP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            12.7,
            const.MEAS_SLEEP_TOWAKEUP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            660.0,
            const.MEAS_SLEEP_TOSLEEP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            760.0,
            const.MEAS_SLEEP_TOWAKEUP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            860.0,
            const.MEAS_SLEEP_HEART_RATE_AVERAGE
        )
        await self.assert_sensor_equals(
            960.0,
            const.MEAS_SLEEP_HEART_RATE_MIN
        )
        await self.assert_sensor_equals(
            1060.0,
            const.MEAS_SLEEP_HEART_RATE_MAX
        )
        await self.assert_sensor_equals(
            1160.0,
            const.MEAS_SLEEP_RESPIRATORY_RATE_AVERAGE
        )
        await self.assert_sensor_equals(
            1260.0,
            const.MEAS_SLEEP_RESPIRATORY_RATE_MIN
        )
        await self.assert_sensor_equals(
            1360.0,
            const.MEAS_SLEEP_RESPIRATORY_RATE_MAX
        )

    async def assert_sensor_equals(self, expected, measure):
        """Assert the state of a withings sensor."""
        sensor = WithingsHealthSensor(
            self.data_manager,
            WITHINGS_MEASUREMENTS_MAP[measure]
        )

        await sensor.async_update()
        assert sensor.state == expected, \
            'Expected %s but was %s for measure: %s.' % (
                expected,
                sensor.state,
                measure
            )


def new_sleep_data(model, series):
    """Create simple dict to simulate api data."""
    return {
        'series': series,
        'model': model
    }


def new_sleep_data_serie(startdate, enddate, state):
    """Create simple dict to simulate api data."""
    return {
        'startdate': startdate,
        'enddate': enddate,
        'state': state
    }


def new_sleep_summary(timezone,
                      model,
                      startdate,
                      enddate,
                      date,
                      modified,
                      data):
    """Create simple dict to simulate api data."""
    return {
        'timezone': timezone,
        'model': model,
        'startdate': startdate,
        'enddate': enddate,
        'date': date,
        'modified': modified,
        'data': data,
    }


def new_sleep_summary_detail(wakeupduration,
                             lightsleepduration,
                             deepsleepduration,
                             remsleepduration,
                             wakeupcount,
                             durationtosleep,
                             durationtowakeup,
                             hr_average,
                             hr_min,
                             hr_max,
                             rr_average,
                             rr_min,
                             rr_max):
    """Create simple dict to simulate api data."""
    return {
        'wakeupduration': wakeupduration,
        'lightsleepduration': lightsleepduration,
        'deepsleepduration': deepsleepduration,
        'remsleepduration': remsleepduration,
        'wakeupcount': wakeupcount,
        'durationtosleep': durationtosleep,
        'durationtowakeup': durationtowakeup,
        'hr_average': hr_average,
        'hr_min': hr_min,
        'hr_max': hr_max,
        'rr_average': rr_average,
        'rr_min': rr_min,
        'rr_max': rr_max,
    }


def new_measure_group(grpid,
                      attrib,
                      date,
                      created,
                      category,
                      deviceid,
                      more,
                      offset,
                      measures):
    """Create simple dict to simulate api data."""
    return {
        'grpid': grpid,
        'attrib': attrib,
        'date': date,
        'created': created,
        'category': category,
        'deviceid': deviceid,
        'measures': measures,
        'more': more,
        'offset': offset,
        'comment': 'blah'  # deprecated
    }


def new_measure(type_str, value, unit):
    """Create simple dict to simulate api data."""
    return {
        'value': value,
        'type': type_str,
        'unit': unit,
        'algo': -1,  # deprecated
        'fm': -1,  # deprecated
        'fw': -1  # deprecated
    }
