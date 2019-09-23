"""Config flow to configure Samsung TV."""
from collections import OrderedDict
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_ID, CONF_MAC, CONF_NAME
from homeassistant.components.ssdp import (
    ATTR_HOST,
    ATTR_NAME,
    ATTR_MODEL_NAME,
    ATTR_MANUFACTURER,
    ATTR_UDN,
)

from .const import CONF_MANUFACTURER, CONF_MODEL, DOMAIN


@callback
def configured_hosts(hass):
    """Return a set of the configured hosts."""
    return set(
        entry.data.get("mac") for entry in hass.config_entries.async_entries(DOMAIN)
    )


class SamsungTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Samsung TV config flow."""

    def __init__(self):
        """Initialize flow."""
        self._host = None
        self._mac = None
        self._manufacturer = None
        self._model = None
        self._uuid = None
        self._name = None
        self._title = None

    def _get_mac(self, host):
        import socket

        if host is None:
            return
        return socket.gethostbyname(host)

    def _async_get_entry(self):
        return self.async_create_entry(
            title=self._title,
            data={
                CONF_HOST: self._host,
                CONF_MAC: self._mac,
                CONF_NAME: self._name,
                CONF_MANUFACTURER: self._manufacturer,
                CONF_MODEL: self._model,
                CONF_ID: self._uuid,
            },
        )

    async def async_step_user(self, user_input=None, error=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._title = user_input[CONF_NAME]
            self._mac = self._get_mac(self._host)
            return self._async_get_entry()

        fields = OrderedDict()
        fields[vol.Required(CONF_HOST, default=self._host or vol.UNDEFINED)] = str
        fields[vol.Optional(CONF_NAME, default=self._title)] = str

        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_ssdp(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        mac = self.context[CONF_MAC] = self._get_mac(user_input[ATTR_HOST])

        if any(
            mac == flow["context"].get(CONF_MAC) for flow in self._async_in_progress()
        ):
            return self.async_abort(reason="already_in_progress")

        if mac in configured_hosts(self.hass):
            return self.async_abort(reason="already_configured")

        self._host = user_input[ATTR_HOST]
        self._mac = mac
        self._manufacturer = user_input[ATTR_MANUFACTURER]
        self._model = user_input[ATTR_MODEL_NAME]
        if user_input[ATTR_UDN].startswith("uuid:"):
            self._uuid = user_input[ATTR_UDN][5:]
        else:
            self._uuid = user_input[ATTR_UDN]
        self._name = user_input[ATTR_NAME]
        if self._name.startswith("[TV]"):
            self._name = self._name[4:]
        self._title = "{} ({})".format(self._name, self._model)

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return self._async_get_entry()
        return self.async_show_form(
            step_id="confirm", description_placeholders={"title": self._title}
        )
