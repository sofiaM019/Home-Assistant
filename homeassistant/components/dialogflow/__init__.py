"""
Support for Dialogflow webhook.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/dialogflow/
"""
import logging

import voluptuous as vol
from aiohttp import web

from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent, template, config_entry_flow
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['webhook']
DOMAIN = 'dialogflow'

SOURCE = "Home Assistant Dialogflow"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {}
}, extra=vol.ALLOW_EXTRA)


class DialogFlowError(HomeAssistantError):
    """Raised when a DialogFlow error happens."""


async def async_setup(hass, config):
    """Set up Dialogflow component."""
    return True


async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook with Dialogflow requests."""
    message = await request.json()
    api_version = get_api_version(message)

    _LOGGER.debug("Received Dialogflow %s request: %s", api_version, message)

    try:
        response = await async_handle_message(hass, message)
        return b'' if response is None else web.json_response(response)

    except DialogFlowError as err:
        _LOGGER.warning(str(err))
        return web.json_response(
            dialogflow_error_response(message, str(err))
        )

    except intent.UnknownIntent as err:
        _LOGGER.warning(str(err))
        return web.json_response(
            dialogflow_error_response(
                message,
                "This intent is not yet configured within Home Assistant."
            )
        )

    except intent.InvalidSlotInfo as err:
        _LOGGER.warning(str(err))
        return web.json_response(
            dialogflow_error_response(
                message,
                "Invalid slot information received for this intent."
            )
        )

    except intent.IntentError as err:
        _LOGGER.warning(str(err))
        return web.json_response(
            dialogflow_error_response(message, "Error handling intent."))


async def async_setup_entry(hass, entry):
    """Configure based on config entry."""
    hass.components.webhook.async_register(
        DOMAIN, 'DialogFlow', entry.data[CONF_WEBHOOK_ID], handle_webhook)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.components.webhook.async_unregister(entry.data[CONF_WEBHOOK_ID])
    return True

config_entry_flow.register_webhook_flow(
    DOMAIN,
    'Dialogflow Webhook',
    {
        'dialogflow_url': 'https://dialogflow.com/docs/fulfillment#webhook',
        'docs_url': 'https://www.home-assistant.io/components/dialogflow/'
    }
)


def get_api_version(message):
    """Help determine the version of Dialogflow request."""
    if message.get('id') is not None:
        return 'V1'

    if message.get('responseId') is not None:
        return 'V2'

    return None


def dialogflow_error_response(message, error):
    """Return a response saying the error message."""
    api_version = get_api_version(message)
    req = {}

    if api_version == 'V2':
        req = message.get('queryResult')

    elif api_version == 'V1':
        req = message.get('result')

    parameters = req.get('parameters').copy()
    dialogflow_response = DialogflowResponse(parameters, api_version)
    dialogflow_response.add_speech(error)
    return dialogflow_response.as_dict()


async def async_handle_message(hass, message):
    """Handle a DialogFlow message."""
    api_version = get_api_version(message)
    req = {}

    if api_version == 'V2':
        req = message.get('queryResult')
        if not req.get('allRequiredParamsPresent', False):
            return None

    elif api_version == 'V1':
        req = message.get('result')
        if req.get('actionIncomplete', True):
            return None

    else:
        return None

    action = req.get('action', '')
    parameters = req.get('parameters').copy()
    parameters["dialogflow_query"] = message
    dialogflow_response = DialogflowResponse(parameters, api_version)

    if action == "":
        raise DialogFlowError(
            "You have not defined an action in your Dialogflow intent.")

    intent_response = await intent.async_handle(
        hass, DOMAIN, action,
        {key: {'value': value} for key, value
         in parameters.items()})

    if 'plain' in intent_response.speech:
        dialogflow_response.add_speech(
            intent_response.speech['plain']['speech'])

    return dialogflow_response.as_dict()


class DialogflowResponse:
    """Help generating the response for Dialogflow."""

    def __init__(self, parameters, api_version):
        """Initialize the Dialogflow response."""
        self.speech = None
        self.parameters = {}
        self.api_version = api_version
        # Parameter names replace '.' and '-' for '_'
        for key, value in parameters.items():
            underscored_key = key.replace('.', '_').replace('-', '_')
            self.parameters[underscored_key] = value

    def add_speech(self, text):
        """Add speech to the response."""
        assert self.speech is None

        if isinstance(text, template.Template):
            text = text.async_render(self.parameters)

        self.speech = text

    def as_dict(self):
        """Return response in a Dialogflow valid dictionary."""
        if self.api_version == 'V2':
            return {
                'fulfillmentText': self.speech,
                'fulfillmentMessages': [
                    {
                        'text': {
                            'text': [self.speech]
                        }
                    }
                ],
                'source': SOURCE
            }

        if self.api_version == 'V1':
            return {
                'speech': self.speech,
                'displayText': self.speech,
                'source': SOURCE
            }

        return {
            'source': SOURCE
        }
