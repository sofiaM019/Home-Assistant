"""Config flow to configure the OpenUV component."""

import os

from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.util.json import load_json

from .local_auth import MonzoAuthCallbackView
from .const import DOMAIN

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'

MONZO_AUTH_START = '/api/monzo'
MONZO_AUTH_CALLBACK_PATH = '/api/monzo/callback'

@callback
def configured_instances(hass):
    """Return a set of configured Monzo instances."""
    return set(
        '{0}'.format(
            entry.data[CONF_CLIENT_ID]
            for entry in hass.config_entries.async_entries(DOMAIN)))


@config_entries.HANDLERS.register(DOMAIN)
class MonzoFlowHandler(config_entries.ConfigFlow):
    """Handle an OpenUV config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        pass

    async def async_step_init(self, user_input=None):
        """Handle the start of the config flow."""
        errors = {}
        print(user_input)
        if user_input is not None:
            client_id = user_input.get(CONF_CLIENT_ID, None)
            client_secret = user_input.get(CONF_CLIENT_SECRET, None)

            if client_id in configured_instances(self.hass):
                errors['base'] = 'identifier_exists'
            else:
                return await self.async_step_link(user_input)
                errors['base'] = 'invalid_api_key'

        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_CLIENT_ID)] = cv.string
        data_schema[vol.Required(CONF_CLIENT_SECRET)] = cv.string

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Monzo account.

        Route the user to a website to authenticate with Monzo. Depending on
        implementation type we expect a pin or an external component to
        deliver the authentication code.
        """
        from monzo import MonzoOAuth2Client

        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        #flow = self.hass.data[DATA_FLOW_IMPL][self.flow_impl]
        print('user_input')
        print(user_input)
        errors = {}


        hass = user_input['hass']
        if user_input is not None:
            try:
                client_id = user_input.get(CONF_CLIENT_ID, None)
                client_secret = user_input.get(CONF_CLIENT_SECRET, None)
                redirect_uri = '{}{}'.format(hass.config.api.base_url,
                    MONZO_AUTH_CALLBACK_PATH)

                oauth = MonzoOAuth2Client(client_id=client_id,
                                          client_secret=client_secret,
                                          redirect_uri=redirect_uri)

                monzo_auth_start_url, _ = oauth.authorize_token_url()

                hass.http.register_redirect(MONZO_AUTH_START,
                                            monzo_auth_start_url)
                hass.http.register_view(MonzoAuthCallbackView(
                    self.async_step_import, oauth))
            except:
                pass

        print(MONZO_AUTH_START)
        monzo_auth_start_redirect = '{}{}'.format(hass.config.api.base_url,
                            MONZO_AUTH_START)
        return self.async_show_form(
            step_id='link',
            description_placeholders={
                'url': monzo_auth_start_redirect
            },
            errors=errors,
        )

    async def async_step_import(self, info):
        """Import existing auth from Monzo."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        config_path = info['monzo_conf_path']

        if not await self.hass.async_add_job(os.path.isfile, config_path):
            self.flow_impl = DOMAIN
            return await self.async_step_link(info)

        #flow = self.hass.data[DATA_FLOW_IMPL][DOMAIN]
        flow = None
        tokens = await self.hass.async_add_job(load_json, config_path)

        if not tokens:
            return await self.async_step_link(info)

        return self._entry_from_tokens(
            'Monzo (import from configuration.yaml)', flow, tokens)

    @callback
    def _entry_from_tokens(self, title, flow, tokens):
        """Create an entry from tokens."""
        return self.async_create_entry(
            title=title,
            data={
                'tokens': tokens,
                #'impl_domain': flow['domain'],
            },
        )
