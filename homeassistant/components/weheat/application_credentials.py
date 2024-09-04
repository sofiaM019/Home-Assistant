"""application_credentials platform the Weheat integration."""

from json import JSONDecodeError
from typing import Any, cast

from aiohttp import ClientError

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ERROR,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2Implementation,
)

from .const import API_SCOPE, ERROR_DESCRIPTION, OAUTH2_AUTHORIZE, OAUTH2_TOKEN


class WeheatOAuth2Implementation(LocalOAuth2Implementation):
    """Weheat variant of LocalOAuth2Implementation to support a keycloak specific error message."""

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": API_SCOPE}

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)

        data[CONF_CLIENT_ID] = self.client_id

        if self.client_secret is not None:
            data[CONF_CLIENT_SECRET] = self.client_secret

        resp = await session.post(self.token_url, data=data)
        if resp.status >= 400:
            try:
                error_response = await resp.json()
            except (ClientError, JSONDecodeError):
                error_response = {}
            error_code = error_response.get(CONF_ERROR, STATE_UNKNOWN)
            error_description = error_response.get(ERROR_DESCRIPTION, STATE_UNKNOWN)

            # Raise a ConfigEntryAuthFailed as the sessions is no longer valid
            raise ConfigEntryAuthFailed(
                f"Token request for {self.domain} failed ({resp.status}:{error_code}): {error_description}"
            )
        resp.raise_for_status()
        return cast(dict, await resp.json())


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return a custom auth implementation."""
    return WeheatOAuth2Implementation(
        hass,
        domain=auth_domain,
        client_id=credential.client_id,
        client_secret=credential.client_secret,
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )
