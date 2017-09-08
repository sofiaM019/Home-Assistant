"""
Support for Satel Integra devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/alarmdecoder/
"""
# pylint: disable=invalid-name

import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED)

REQUIREMENTS = ['satel_integra==0.1.0']

DEFAULT_ALARM_NAME = 'satel_integra'
DEFAULT_PORT = 7094
DEFAULT_CONF_ARM_HOME_MODE = 1
DEFAULT_DEVICE_PARTITION = 1
DEFAULT_ZONE_TYPE = 'motion'

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'satel_integra'

DATA_AD = 'satel_integra'

CONF_DEVICE_HOST = 'host'
CONF_DEVICE_PORT = 'port'
CONF_DEVICE_PARTITION = 'partition'
CONF_ARM_HOME_MODE = 'arm_home_mode'
CONF_ZONE_NAME = 'name'
CONF_ZONE_TYPE = 'type'
CONF_ZONES = 'zones'

ZONES = 'zones'

SIGNAL_PANEL_MESSAGE = 'satel_integra.panel_message'
SIGNAL_PANEL_ARM_AWAY = 'satel_integra.panel_arm_away'
SIGNAL_PANEL_ARM_HOME = 'satel_integra.panel_arm_home'
SIGNAL_PANEL_DISARM = 'satel_integra.panel_disarm'

SIGNAL_ZONES_UPDATED = 'satel_integra.zones_updated'

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_ZONE_NAME): cv.string,
    vol.Optional(CONF_ZONE_TYPE, default=DEFAULT_ZONE_TYPE): cv.string})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE_HOST): cv.string,
        vol.Optional(CONF_DEVICE_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_DEVICE_PARTITION,
                     default=DEFAULT_DEVICE_PARTITION): cv.positive_int,
        vol.Optional(CONF_ARM_HOME_MODE,
                     default=DEFAULT_CONF_ARM_HOME_MODE): vol.In([1, 2, 3]),
        vol.Optional(CONF_ZONES): {vol.Coerce(int): ZONE_SCHEMA},
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up for the Satel Integra devices."""
    conf = config.get(DOMAIN)

    zones = conf.get(CONF_ZONES)
    controller = False
    host = conf.get(CONF_DEVICE_HOST)
    port = conf.get(CONF_DEVICE_PORT)
    partition = conf.get(CONF_DEVICE_PARTITION)

    from satel_integra.satel_integra import AsyncSatel
    controller = AsyncSatel(host, port, zones, hass.loop, partition)

    hass.data[DATA_AD] = controller

    result = yield from controller.connect()

    if not result:
        return False

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                               lambda s: controller.close())

    _LOGGER.debug("Arm home config: %s, mode: %s ",
                  conf,
                  conf.get(CONF_ARM_HOME_MODE))

    yield from async_load_platform(hass, 'alarm_control_panel',
                                   DOMAIN, conf, config)

    yield from async_load_platform(hass, 'binary_sensor',
                                   DOMAIN, {CONF_ZONES: zones}, config)

    @callback
    def alarm_status_update_callback(status):
        """Send status update received from alarm to home assistant."""
        _LOGGER.info("Alarm status callback, status: %s", status)
        hass_alarm_status = STATE_ALARM_DISARMED

        from satel_integra.satel_integra import AlarmState

        if status == AlarmState.ARMED_MODE0:
            hass_alarm_status = STATE_ALARM_ARMED_AWAY

        elif status in [
                AlarmState.ARMED_MODE0,
                AlarmState.ARMED_MODE1,
                AlarmState.ARMED_MODE2,
                AlarmState.ARMED_MODE3
        ]:
            hass_alarm_status = STATE_ALARM_ARMED_HOME

        elif status in [AlarmState.TRIGGERED, AlarmState.TRIGGERED_FIRE]:
            hass_alarm_status = STATE_ALARM_TRIGGERED

        elif status == AlarmState.DISARMED:
            hass_alarm_status = STATE_ALARM_DISARMED

        _LOGGER.info("Sending hass_alarm_status: %s...", hass_alarm_status)
        async_dispatcher_send(hass, SIGNAL_PANEL_MESSAGE, hass_alarm_status)

    @callback
    def zones_update_callback(status):
        """Update zone objects as per notification from the alarm."""
        _LOGGER.debug("Zones callback , status: %s", status)
        async_dispatcher_send(hass, SIGNAL_ZONES_UPDATED, status[ZONES])

    try:
        from asyncio import ensure_future as asyncio_ensure_future
    except ImportError:
        from asyncio import async as asyncio_ensure_future
    # pylint: disable=deprecated-method

    hass.async_add_job(asyncio_ensure_future(controller.keep_alive()))
    hass.async_add_job(asyncio_ensure_future(
        controller.monitor_status(
            alarm_status_update_callback,
            zones_update_callback)
    )
                      )

    return True
