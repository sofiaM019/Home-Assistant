"""Support for (EMEA/EU-based) Honeywell evohome systems."""
# Glossary:
#   TCS - temperature control system (a.k.a. Controller, Parent), which can
#   have up to 13 Children:
#     0-12 Heating zones (a.k.a. Zone), and
#     0-1 DHW controller, (a.k.a. Boiler)
# The TCS & Zones are implemented as Climate devices, Boiler as a WaterHeater
from datetime import timedelta
import logging

from requests import ConnectionError, HTTPError
import voluptuous as vol

from homeassistant.const import (
    CONF_SCAN_INTERVAL, CONF_USERNAME, CONF_PASSWORD,
    EVENT_HOMEASSISTANT_START,
    HTTP_BAD_REQUEST, HTTP_SERVICE_UNAVAILABLE, HTTP_TOO_MANY_REQUESTS
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

REQUIREMENTS = ['evohomeclient==0.3.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'evohome'
DATA_EVOHOME = 'data_' + DOMAIN
DISPATCHER_EVOHOME = 'dispatcher_' + DOMAIN

CONF_LOCATION_IDX = 'location_idx'
SCAN_INTERVAL_DEFAULT = timedelta(seconds=300)
SCAN_INTERVAL_MINIMUM = timedelta(seconds=180)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL_DEFAULT):
            vol.All(cv.time_period, vol.Range(min=SCAN_INTERVAL_MINIMUM)),
    }),
}, extra=vol.ALLOW_EXTRA)

CONF_SECRETS = [
    CONF_USERNAME, CONF_PASSWORD,
]

# These are used to help prevent E501 (line too long) violations.
GWS = 'gateways'
TCS = 'temperatureControlSystems'

# bit masks for dispatcher packets
EVO_PARENT = 0x01
EVO_CHILD = 0x02


def setup(hass, hass_config):
    """Create a (EMEA/EU-based) Honeywell evohome system.

    Currently, only the Controller and the Zones are implemented here.
    """
    evo_data = hass.data[DATA_EVOHOME] = {}
    evo_data['timers'] = {}

    # use a copy, since scan_interval is rounded up to nearest 60s
    evo_data['params'] = dict(hass_config[DOMAIN])
    scan_interval = evo_data['params'][CONF_SCAN_INTERVAL]
    scan_interval = timedelta(
        minutes=(scan_interval.total_seconds() + 59) // 60)

    from evohomeclient2 import EvohomeClient

    try:
        client = evo_data['client'] = EvohomeClient(
            evo_data['params'][CONF_USERNAME],
            evo_data['params'][CONF_PASSWORD],
            debug=False
        )

    except ConnectionError:
        _LOGGER.error(
            "setup(): Failed to connect with the vendor's web servers. "
            "The server is not contactable (maybe the vendor's fault?). "
            "Unable to continue. Resolve any errors and restart HA."
        )
        raise  # Expose the actual exception to the user

    except HTTPError as err:
        if err.response.status_code == HTTP_BAD_REQUEST:
            _LOGGER.error(
                "setup(): Failed to connect with the vendor's web servers. "
                "Check your username (%s), and password are correct. "
                "Unable to continue. Resolve any errors and restart HA.",
                evo_data['params'][CONF_USERNAME]
            )

        elif err.response.status_code == HTTP_SERVICE_UNAVAILABLE:
            _LOGGER.error(
                "setup(): Failed to connect with the vendor's web servers. "
                "The vendor says the server is currently unavailable. "
                "Unable to continue. Wait a while and restart HA."
            )

        elif err.response.status_code == HTTP_TOO_MANY_REQUESTS:
            _LOGGER.error(
                "setup(): Failed to connect with the vendor's web servers. "
                "The vendor's API rate limit has been exceeded. "
                "Unable to continue. Wait a while and restart HA."
            )

        else:
            raise  # we don't expect/handle any other HTTPErrors

        return False

    finally:  # Redact any config data that's no longer needed
        for parameter in CONF_SECRETS:
            evo_data['params'][parameter] = 'REDACTED' \
                if evo_data['params'][parameter] else None

    evo_data['status'] = {}

    # Redact any installation data that's no longer needed
    for loc in client.installation_info:
        loc['locationInfo']['locationId'] = 'REDACTED'
        loc['locationInfo']['locationOwner'] = 'REDACTED'
        loc['locationInfo']['streetAddress'] = 'REDACTED'
        loc['locationInfo']['city'] = 'REDACTED'
        loc[GWS][0]['gatewayInfo'] = 'REDACTED'

    # Pull down the installation configuration
    loc_idx = evo_data['params'][CONF_LOCATION_IDX]
    try:
        evo_data['config'] = client.installation_info[loc_idx]

    except IndexError:
        _LOGGER.error(
            "setup(): Invalid configuration (unknown location). "
            "Parameter '%s'=%s, is outside its valid range (0-%s). "
            "Unable to continue. Fix any configuration errors and restart HA.",
            CONF_LOCATION_IDX, loc_idx, len(client.installation_info) - 1
        )
        return False

    if _LOGGER.isEnabledFor(logging.DEBUG):
        tmp_loc = dict(evo_data['config'])
        tmp_loc['locationInfo']['postcode'] = 'REDACTED'

        if 'dhw' in tmp_loc[GWS][0][TCS][0]:  # if this location has DHW...
            tmp_loc[GWS][0][TCS][0]['dhw'] = '...'

        _LOGGER.debug("setup(): evo_data['config']=%s", tmp_loc)

    load_platform(hass, 'climate', DOMAIN, {}, hass_config)

    if 'dhw' in evo_data['config'][GWS][0][TCS][0]:
        _LOGGER.warning(
            "setup(): DHW found, but this component doesn't support DHW."
        )

    @callback
    def _first_update(event):
        """When HA has started, the hub knows to retrieve it's first update."""
        pkt = {'sender': 'setup()', 'signal': 'refresh', 'to': EVO_PARENT}
        async_dispatcher_send(hass, DISPATCHER_EVOHOME, pkt)

    hass.bus.listen(EVENT_HOMEASSISTANT_START, _first_update)

    return True
