"""Support for the YesssSMS platform."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_RECIPIENT, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService

from YesssSMS import YesssSMS

from .const import CONF_PROVIDER, CONF_TEST_LOGIN_DATA

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_RECIPIENT): cv.string,
        vol.Optional(CONF_PROVIDER, default="YESSS"): cv.string,
        vol.Optional(CONF_TEST_LOGIN_DATA, default=True): cv.boolean,
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the YesssSMS notification service."""

    try:
        yesss = YesssSMS(
            config[CONF_USERNAME], config[CONF_PASSWORD], provider=config[CONF_PROVIDER]
        )
    except YesssSMS.UnsupportedProviderError as ex:
        _LOGGER.error("Unknown provider: %s", ex)
        return None

    if config[CONF_TEST_LOGIN_DATA]:
        if yesss.login_data_valid():
            _LOGGER.info("Login data for '%s' valid.", yesss._provider)
        else:
            _LOGGER.error(
                "Login data is not valid! Please double check your login data at %s.",
                yesss._login_url,
            )
            return None

    _LOGGER.debug(
        "initialized; library version: %s, with %s", yesss.version(), yesss._provider
    )
    return YesssSMSNotificationService(yesss, config[CONF_RECIPIENT])


class YesssSMSNotificationService(BaseNotificationService):
    """Implement a notification service for the YesssSMS service."""

    def __init__(self, client, recipient):
        """Initialize the service."""
        self.yesss = client
        self._recipient = recipient

    def send_message(self, message="", **kwargs):
        """Send a SMS message via Yesss.at's website."""
        if self.yesss.account_is_suspended():
            # only retry to login after HASS was restarted with (hopefully)
            # new login data.
            _LOGGER.error(
                "Account is suspended, cannot send SMS. "
                "Check your login data and restart Home Assistant"
            )
            return
        try:
            self.yesss.send(self._recipient, message)
        except self.yesss.NoRecipientError as ex:
            _LOGGER.error(
                "You need to provide a recipient for SMS notification: %s", ex
            )
        except self.yesss.EmptyMessageError as ex:
            _LOGGER.error("Cannot send empty SMS message: %s", ex)
        except self.yesss.SMSSendingError as ex:
            _LOGGER.error(str(ex), exc_info=ex)
        except ConnectionError as ex:
            _LOGGER.error(
                "YesssSMS: unable to connect to yesss.at server.", exc_info=ex
            )
        except self.yesss.AccountSuspendedError as ex:
            _LOGGER.error(
                "Wrong login credentials!! Verify correct credentials and "
                "restart Home Assistant: %s",
                ex,
            )
        except self.yesss.LoginError as ex:
            _LOGGER.error("Wrong login credentials: %s", ex)
        else:
            _LOGGER.info("SMS sent")
