"""
Register an iFrame front end panel.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/panel_iframe/
"""
import asyncio

import voluptuous as vol

from homeassistant.const import (CONF_ICON, CONF_URL)
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['frontend']

DOMAIN = 'panel_iframe'

CONF_TITLE = 'title'

CONF_ABSOLUTE_PATH_ERROR_MSG = "Invalid absolute path in relative URL"
CONF_ABSOLUTE_PATH_REGEX = r'\A/'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: {
            vol.Optional(CONF_TITLE): cv.string,
            vol.Optional(CONF_ICON): cv.icon,
            vol.Required(CONF_URL): vol.Any(
                vol.Match(
                    CONF_ABSOLUTE_PATH_REGEX,
                    msg=CONF_ABSOLUTE_PATH_ERROR_MSG),
                cv.url),
        }})}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def setup(hass, config):
    """Set up the iFrame frontend panels."""
    for url_path, info in config[DOMAIN].items():
        yield from hass.components.frontend.async_register_built_in_panel(
            'iframe', info.get(CONF_TITLE), info.get(CONF_ICON),
            url_path, {'url': info[CONF_URL]})

    return True
