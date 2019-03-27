"""Offer template automation rules."""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (
    CONF_VALUE_TEMPLATE, CONF_PLATFORM, CONF_ENTITY_ID)
from homeassistant.helpers.event import async_track_template
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = IF_ACTION_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'template',
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_ENTITY_ID): cv.comp_entity_ids,
})


async def async_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    value_template = config.get(CONF_VALUE_TEMPLATE)
    value_template.hass = hass
    entity_ids = config.get(CONF_ENTITY_ID)

    @callback
    def template_listener(entity_id, from_s, to_s):
        """Listen for state changes and calls action."""
        hass.async_run_job(action({
            'trigger': {
                'platform': 'template',
                'entity_id': entity_id,
                'from_state': from_s,
                'to_state': to_s,
            },
        }, context=to_s.context))

    return async_track_template(hass, value_template, template_listener,
                                entity_ids=entity_ids)
