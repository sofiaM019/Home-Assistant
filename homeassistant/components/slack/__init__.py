"""The slack integration."""
import logging

from aiohttp.client_exceptions import ClientError
from slack import WebClient
from slack.errors import SlackApiError

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, discovery
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.typing import ConfigType

from .const import DATA_CLIENT, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NOTIFY, Platform.NUMBER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Slack component."""
    # Iterate all entries for notify to only get Slack
    if Platform.NOTIFY in config:
        for entry in config[Platform.NOTIFY]:
            if entry[CONF_PLATFORM] == DOMAIN:
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                    )
                )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Slack from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)
    slack = WebClient(token=entry.data[CONF_API_KEY], run_async=True, session=session)

    try:
        slack.url = (await slack.auth_test())["url"]
        slack.user_id = (await slack.auth_test())["user_id"]
    except (SlackApiError, ClientError) as ex:
        if isinstance(ex, SlackApiError) and ex.response["error"] == "invalid_auth":
            _LOGGER.error("Invalid API key")
            return False
        raise ConfigEntryNotReady("Error while setting up integration") from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data | {DATA_CLIENT: slack}

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            hass.data[DOMAIN][entry.entry_id],
            hass.data[DOMAIN],
        )
    )

    hass.config_entries.async_setup_platforms(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    return True


class SlackEntity(Entity):
    """Representation of a Slack entity."""

    _attr_attribution = "Data provided by Slack"

    def __init__(self, client: WebClient, entry: ConfigEntry) -> None:
        """Initialize a Slack entity."""
        self._attr_device_info = DeviceInfo(
            configuration_url=client.url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
        )
