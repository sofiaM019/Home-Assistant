"""Offer device oriented automation."""
import voluptuous as vol

from homeassistant.components.device_automation import (
    TRIGGER_BASE_SCHEMA,
    async_get_device_automation_platform,
)


# mypy: allow-untyped-defs, no-check-untyped-defs

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA)


async def async_validate_trigger_config(hass, config):
    """Validate config."""
    platform = await async_get_device_automation_platform(hass, config, "trigger")
    return platform.TRIGGER_SCHEMA(config)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for trigger."""
    platform = await async_get_device_automation_platform(hass, config, "trigger")
    return await platform.async_attach_trigger(hass, config, action, automation_info)
