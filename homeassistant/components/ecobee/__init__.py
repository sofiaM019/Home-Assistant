"""Support for ecobee."""
import os
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle

from .const import (
    CONF_HOLD_TEMP,
    CONF_REFRESH_TOKEN,
    DATA_ECOBEE_CONFIG,
    DEFAULT_HOLD_TEMP,
    DOMAIN,
    ECOBEE_PLATFORMS,
    _LOGGER,
)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=180)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_API_KEY): cv.string,
                vol.Optional(CONF_HOLD_TEMP, DEFAULT_HOLD_TEMP): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """
    Ecobee only uses config flow for configuration.

    But, an existing configuration.yaml config and ecobee.conf
    will trigger an import flow if a config entry doesn't
    already exist to help users migrating from the old ecobee
    component.
    """
    from pyecobee import ECOBEE_CONFIG_FILENAME

    if not hass.config_entries.async_entries(DOMAIN) and os.path.isfile(
        hass.config.path(ECOBEE_CONFIG_FILENAME)
    ):
        """Store legacy config."""
        hass.data[DATA_ECOBEE_CONFIG] = config[DOMAIN]
        """No config entry exists and ecobee.conf exists; trigger the import flow."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up ecobee via a config entry."""

    if not entry.options:
        """Loading via config entry for the first time, set up options."""
        await async_populate_options(hass, entry)

    api_key = entry.data[CONF_API_KEY]
    refresh_token = entry.data[CONF_REFRESH_TOKEN]

    data = EcobeeData(hass, entry, api_key=api_key, refresh_token=refresh_token)

    if not await hass.async_add_executor_job(data.refresh):
        return False

    await hass.async_add_executor_job(data.update)

    if data.ecobee.thermostats is None:
        _LOGGER.error("No ecobee devices found to set up.")
        return False

    hass.data[DOMAIN] = data

    for component in ECOBEE_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


class EcobeeData:
    """
    Handle getting the latest data from ecobee.com so platforms can use it.

    Also handle refreshing tokens and updating config entry with refreshed tokens.
    """

    def __init__(self, hass, entry, api_key, refresh_token):
        """Initialize the Ecobee data object."""
        from pyecobee import Ecobee, ECOBEE_API_KEY, ECOBEE_REFRESH_TOKEN

        self._hass = hass
        self._entry = entry
        self.ecobee = Ecobee(
            config={ECOBEE_API_KEY: api_key, ECOBEE_REFRESH_TOKEN: refresh_token}
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from ecobee.com."""
        from pyecobee import ExpiredTokenError

        try:
            self.ecobee.update()
            _LOGGER.debug("Updating ecobee.")
        except ExpiredTokenError:
            _LOGGER.warn("ecobee update failed; attempting to refresh expired tokens.")
            self.refresh()

    def refresh(self) -> bool:
        """Refresh ecobee tokens and update config entry."""
        from pyecobee import ECOBEE_API_KEY, ECOBEE_REFRESH_TOKEN

        _LOGGER.debug("Refreshing ecobee tokens and updating config entry.")
        if self.ecobee.refresh_tokens():
            self._hass.config_entries.async_update_entry(
                self._entry,
                data={
                    CONF_API_KEY: self.ecobee.config[ECOBEE_API_KEY],
                    CONF_REFRESH_TOKEN: self.ecobee.config[ECOBEE_REFRESH_TOKEN],
                },
            )
            return True
        else:
            _LOGGER.error("Error updating ecobee tokens.")
            return False


async def async_populate_options(hass, config_entry):
    """
    Populate options for ecobee. Called by async_setup_entry.

    Options will be initially set to the values specified in
    configuration.yaml, if they exist, or, if not, the default.
    """
    try:
        hold_temp = hass.data[DATA_ECOBEE_CONFIG].get(CONF_HOLD_TEMP, DEFAULT_HOLD_TEMP)
    except KeyError:
        hold_temp = DEFAULT_HOLD_TEMP

    options = {CONF_HOLD_TEMP: hold_temp}

    hass.config_entries.async_update_entry(config_entry, options=options)


async def async_unload_entry(hass, config_entry):
    """Unload the config entry, but store the ecobee API key for later."""
    hass.data.pop(DOMAIN)
    hass.data[DATA_ECOBEE_CONFIG] = {CONF_API_KEY: config_entry.data[CONF_API_KEY]}

    for platform in ECOBEE_PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(config_entry, platform)

    return True
