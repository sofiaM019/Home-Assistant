"""Support for AVM Fritz!Box functions."""
import logging

from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .common import FritzBoxTools
from .const import DOMAIN, SUPPORTED_DOMAINS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up fritzboxtools from config entry."""
    _LOGGER.debug("Setting up FRITZ!Box Tools component")
    fritz_tools = FritzBoxTools(
        hass=hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        await fritz_tools.async_setup()
    except FritzSecurityError as ex:
        raise ConfigEntryAuthFailed from ex
    except FritzConnectionException as ex:
        raise ConfigEntryNotReady from ex

    await fritz_tools.async_start()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = fritz_tools

    @callback
    def _async_unload(event):
        fritz_tools.async_unload()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_unload)
    )
    # Load the other platforms like switch
    for domain in SUPPORTED_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, domain)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigType) -> bool:
    """Unload FRITZ!Box Tools config entry."""
    fritzbox: FritzBoxTools = hass.data[DOMAIN][entry.entry_id]
    fritzbox.async_unload()

    hass.data[DOMAIN].pop(entry.entry_id)

    for domain in SUPPORTED_DOMAINS:
        await hass.config_entries.async_forward_entry_unload(entry, domain)
    return True
