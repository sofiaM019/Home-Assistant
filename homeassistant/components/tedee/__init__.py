"""Init the tedee component."""
from collections.abc import Awaitable, Callable
import logging
from typing import Any

from aiohttp.hdrs import METH_POST
from aiohttp.web import Request, Response
from yarl import URL

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.webhook import (
    async_generate_id as webhook_generate_id,
    async_generate_url as webhook_generate_url,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, NAME
from .coordinator import TedeeApiCoordinator

PLATFORMS = [
    Platform.LOCK,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration setup."""

    if CONF_WEBHOOK_ID not in entry.data:
        new_data = entry.data.copy()
        new_data[CONF_WEBHOOK_ID] = webhook_generate_id()
        hass.config_entries.async_update_entry(entry, data=new_data)

    coordinator = TedeeApiCoordinator(hass)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    webhook_registered = False

    async def unregister_webhook(_: Any) -> None:
        nonlocal webhook_registered
        if not webhook_registered:
            return
        await coordinator.tedee_client.delete_webhooks()
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
        _LOGGER.debug("Unregistered Tedee webhook")

    async def register_webhook(_: Any) -> None:
        nonlocal webhook_registered
        if webhook_registered:
            return
        webhook_url = webhook_generate_url(hass, entry.data[CONF_WEBHOOK_ID])
        url = URL(webhook_url)
        if url.scheme != "https" or url.port != 443:
            _LOGGER.warning(
                "Webhook not registered - "
                "https and port 443 is required to register the webhook"
            )
            return
        webhook_name = "Tedee"
        if entry.title != NAME:
            webhook_name = f"{NAME} {entry.title}"

        webhook_register(
            hass,
            DOMAIN,
            webhook_name,
            entry.data[CONF_WEBHOOK_ID],
            get_webhook_handler(coordinator),
            allowed_methods=[METH_POST],
        )
        _LOGGER.debug("Registered Withings webhook at hass: %s", webhook_url)

        await coordinator.tedee_client.register_webhook(webhook_url)
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)
        )
        webhook_registered = True

    await register_webhook(None)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def json_message_response(message: str, message_code: int) -> Response:
    """Produce common json output."""
    return HomeAssistantView.json({"message": message, "code": message_code})


def get_webhook_handler(
    coordinator: TedeeApiCoordinator,
) -> Callable[[HomeAssistant, str, Request], Awaitable[Response | None]]:
    """Return webhook handler."""

    async def async_webhook_handler(
        hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response | None:
        # Handle http post calls to the path.
        if not request.body_exists:
            return json_message_response("No request body", message_code=12)

        body = await request.json()
        coordinator.tedee_client.parse_webhook_message(body)
        coordinator.async_update_listeners()

        return json_message_response("Success", message_code=0)

    return async_webhook_handler
