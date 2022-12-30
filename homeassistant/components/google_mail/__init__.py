"""Support for Google Mail."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from aiohttp.client_exceptions import ClientError, ClientResponseError
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.service import async_extract_config_entry_ids
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ENABLED,
    ATTR_END,
    ATTR_MESSAGE,
    ATTR_PLAIN_TEXT,
    ATTR_RESTRICT_CONTACTS,
    ATTR_RESTRICT_DOMAIN,
    ATTR_START,
    ATTR_TITLE,
    DATA_HASS_CONFIG,
    DATA_SESSION,
    DEFAULT_ACCESS,
    DOMAIN,
)

PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]

SERVICE_EMAIL = "email"
SERVICE_SET_VACATION = "set_vacation"

SERVICE_VACATION_SCHEMA = vol.All(
    cv.make_entity_service_schema(
        {
            vol.Required(ATTR_ENABLED, default=True): cv.boolean,
            vol.Optional(ATTR_TITLE): cv.string,
            vol.Required(ATTR_MESSAGE): cv.string,
            vol.Optional(ATTR_PLAIN_TEXT, default=True): cv.boolean,
            vol.Optional(ATTR_RESTRICT_CONTACTS): cv.boolean,
            vol.Optional(ATTR_RESTRICT_DOMAIN): cv.boolean,
            vol.Optional(ATTR_START): cv.date,
            vol.Optional(ATTR_END): cv.date,
        },
    )
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Mail from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                "OAuth session is not valid, reauth required"
            ) from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err

    if not async_entry_has_scopes(hass, entry):
        raise ConfigEntryAuthFailed("Required scopes are not present, reauth required")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data | {
        DATA_SESSION: session
    }

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            hass.data[DOMAIN][entry.entry_id] | {CONF_NAME: entry.title},
            hass.data[DATA_HASS_CONFIG],
        )
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    async def extract_gmail_config_entries(call: ServiceCall) -> list[ConfigEntry]:
        return [
            entry
            for entry_id in await async_extract_config_entry_ids(hass, call)
            if (entry := hass.config_entries.async_get_entry(entry_id))
            and entry.domain == DOMAIN
        ]

    def _set_vacation(call: ServiceCall, service: Resource) -> None:
        """Run vacation call in the executor."""
        settings = {
            "enableAutoReply": call.data[ATTR_ENABLED],
            "responseSubject": call.data.get(ATTR_TITLE),
        }
        if contacts := call.data.get(ATTR_RESTRICT_CONTACTS):
            settings["restrictToContacts"] = contacts
        if domain := call.data.get(ATTR_RESTRICT_DOMAIN):
            settings["restrictToDomain"] = domain
        if _date := call.data.get(ATTR_START):
            _dt = datetime.combine(_date, datetime.min.time())
            settings["startTime"] = _dt.timestamp() * 1000
        if _date := call.data.get(ATTR_END):
            _dt = datetime.combine(_date, datetime.min.time())
            settings["endTime"] = (_dt + timedelta(days=1)).timestamp() * 1000
        if call.data[ATTR_PLAIN_TEXT]:
            settings["responseBodyPlainText"] = call.data[ATTR_MESSAGE]
        else:
            settings["responseBodyHtml"] = call.data[ATTR_MESSAGE]
        _settings = service.users().settings()  # pylint: disable=no-member
        _settings.updateVacation(userId="me", body=settings).execute()

    async def gmail_service(call: ServiceCall) -> None:
        """Call Google Mail service."""
        for entry in await extract_gmail_config_entries(call):
            if not (data := hass.data[DOMAIN].get(entry.entry_id)):
                raise ValueError(f"Config entry not loaded: {entry.entry_id}")
            service = await get_oauth_service(data)
            try:
                await hass.async_add_executor_job(_set_vacation, call, service)
            except RefreshError as ex:
                entry.async_start_reauth(hass)
                raise ex

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_VACATION,
        schema=SERVICE_VACATION_SCHEMA,
        service_func=gmail_service,
    )

    return True


async def get_oauth_service(data: dict[str, Any]) -> Resource:
    """Get valid service with latest access token."""
    session: OAuth2Session = data[DATA_SESSION]
    await session.async_ensure_token_valid()
    credentials = Credentials(data[CONF_TOKEN][CONF_ACCESS_TOKEN])
    return build("gmail", "v1", credentials=credentials)


def async_entry_has_scopes(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verify that the config entry desired scope is present in the oauth token."""
    return all(
        feature in entry.data[CONF_TOKEN]["scope"].split(" ")
        for feature in DEFAULT_ACCESS
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        for service_name in hass.services.async_services()[DOMAIN]:
            hass.services.async_remove(DOMAIN, service_name)

    return unload_ok
