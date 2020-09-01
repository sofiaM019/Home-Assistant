"""Errors for the HLK-SW16 component."""
from homeassistant.exceptions import HomeAssistantError


class SW16Exception(HomeAssistantError):
    """Base class for HLK-SW16 exceptions."""


class AlreadyConfigured(SW16Exception):
    """HLK-SW16 is already configured."""


class CannotConnect(SW16Exception):
    """Unable to connect to the HLK-SW16."""
