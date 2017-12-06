"""
Support for WebDav Calendar.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/calendar.caldav/
"""


import logging
from datetime import (timedelta, datetime)
import re
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.calendar import (
    CalendarEventDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, CONF_URL, CONF_USERNAME, CONF_PASSWORD)

from homeassistant.util import dt, Throttle

REQUIREMENTS = ['caldav==0.5.0']

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE_ID = 'device_id'
CONF_CALENDARS = 'calendars'
CONF_CUSTOM_CALENDARS = 'custom_calendars'
CONF_CALENDAR = 'calendar'
CONF_ALL_DAY = 'all_day'
CONF_SEARCH = 'search'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): vol.Url(),
    vol.Optional(CONF_CALENDARS, default=[]):
        vol.All(cv.ensure_list, vol.Schema([
            cv.string
        ])),
    vol.Inclusive(CONF_USERNAME, 'authentication'): cv.string,
    vol.Inclusive(CONF_PASSWORD, 'authentication'): cv.string,
    vol.Optional(CONF_CUSTOM_CALENDARS, default=[]):
        vol.All(cv.ensure_list, vol.Schema([
            vol.Schema({
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_CALENDAR): cv.string,
                vol.Required(CONF_SEARCH): cv.string
            })
        ]))
})

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


def setup_platform(hass, config, add_devices, disc_info=None):
    """Set up the WebDav Calendar platform."""
    import caldav

    client = caldav.DAVClient(config.get(CONF_URL),
                              None,
                              config.get(CONF_USERNAME),
                              config.get(CONF_PASSWORD))

    # Retrieve all the remote calendars
    calendars = client.principal().calendars()

    calendar_devices = []
    for calendar in list(calendars):
        # If a calendar name was given in the configuration,
        # ignore all the others
        if (config.get(CONF_CALENDARS)
                and calendar.name not in config.get(CONF_CALENDARS)):
            _LOGGER.debug("Ignoring calendar '%s'", calendar.name)
            continue

        # Create additional calendars based on custom filtering
        # rules
        if config.get(CONF_CUSTOM_CALENDARS) is not None:
            for cust_calendar in list(config.get(CONF_CUSTOM_CALENDARS)):
                # Check that the base calendar matches
                if cust_calendar.get(CONF_CALENDAR) != calendar.name:
                    continue

                device_data = {
                    CONF_NAME: cust_calendar.get(CONF_NAME),
                    CONF_DEVICE_ID: "%s %s" % (
                        cust_calendar.get(CONF_CALENDAR),
                        cust_calendar.get(CONF_NAME)),
                }

                calendar_devices.append(
                    WebDavCalendarEventDevice(hass,
                                              device_data,
                                              calendar,
                                              cust_calendar.get(CONF_ALL_DAY),
                                              cust_calendar.get(CONF_SEARCH))
                )
        else:
            device_data = {
                CONF_NAME: calendar.name,
                CONF_DEVICE_ID: calendar.name
            }
            calendar_devices.append(
                WebDavCalendarEventDevice(hass, device_data, calendar)
            )

    # Finally add all the calendars we've created
    add_devices(calendar_devices)


class WebDavCalendarEventDevice(CalendarEventDevice):
    """A device for getting the next Task from a WebDav Calendar."""

    def __init__(self,
                 hass,
                 device_data,
                 calendar,
                 all_day=False,
                 search=None):
        """Create the WebDav Calendar Event Device."""
        self.data = WebDavCalendarData(calendar, all_day, search)
        super().__init__(hass, device_data)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.data.event is None:
            # No tasks, we don't REALLY need to show anything.
            return {}

        attributes = super().device_state_attributes
        return attributes


class WebDavCalendarData(object):
    """Class to utilize the calendar dav client object to get next event."""

    def __init__(self, calendar, include_all_day, search):
        """Set up how we are going to search the WebDav calendar."""
        self.calendar = calendar
        self.include_all_day = include_all_day
        self.search = search
        self.event = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data."""
        # We have to retrieve the results for the whole day as the server
        # won't return events that have already started
        results = self.calendar.date_search(
            dt.start_of_local_day(),
            dt.start_of_local_day() + timedelta(days=1)
        )

        # dtstart can be a date or datetime depending if the event lasts a
        # whole day. Convert everything to datetime to be able to sort it
        results.sort(key=lambda x: self.to_datetime(
            x.instance.vevent.dtstart.value
        ))

        vevent = None
        for event in results:
            if (self.is_matching(event.instance.vevent, self.search)
                    and (not self.is_all_day(event.instance.vevent)
                         or self.include_all_day)
                    and not self.is_over(event.instance.vevent)):
                vevent = event.instance.vevent
                break

        # If no matching event could be found
        if vevent is None:
            _LOGGER.info(
                "No matching event found in the %d results for %s",
                len(results),
                self.calendar.name,
            )
            self.event = None
            return True

        # Populate the entity attributes with the event values
        self.event = {
            "summary": vevent.summary.value,
            "start": self.get_hass_date(vevent.dtstart.value),
            "end": self.get_hass_date(vevent.dtend.value),
            "location": self.get_attr_value(vevent, "location"),
            "description": self.get_attr_value(vevent, "description")
        }
        return True

    @staticmethod
    def is_matching(vevent, search):
        """Return if the event matches the filter critera."""
        if search is None:
            return True

        pattern = re.compile(search)
        return (hasattr(vevent, "summary")
                and pattern.match(vevent.summary.value)
                or hasattr(vevent, "location")
                and pattern.match(vevent.location.value)
                or hasattr(vevent, "description")
                and pattern.match(vevent.description.value))

    @staticmethod
    def is_all_day(vevent):
        """Return if the event last the whole day."""
        return not isinstance(vevent.dtstart.value, datetime)

    @staticmethod
    def is_over(vevent):
        """Return if the event is over."""
        return dt.now() > WebDavCalendarData.to_datetime(vevent.dtend.value)

    @staticmethod
    def get_hass_date(obj):
        """Return if the event matches."""
        if isinstance(obj, datetime):
            return {"dateTime": obj.isoformat()}

        return {"date": obj.isoformat()}

    @staticmethod
    def to_datetime(obj):
        """Return a datetime."""
        if isinstance(obj, datetime):
            return obj
        return dt.as_local(dt.dt.datetime.combine(obj, dt.dt.time.min))

    @staticmethod
    def get_attr_value(obj, attribute):
        """Return the value of the attribute if defined."""
        if hasattr(obj, attribute):
            return getattr(obj, attribute).value
        return None
