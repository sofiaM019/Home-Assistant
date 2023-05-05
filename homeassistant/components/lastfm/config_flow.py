"""Config flow for LastFm."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pylast import LastFMNetwork, User, WSError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_MAIN_USER, CONF_USERS, DOMAIN

PLACEHOLDERS = {"api_account_url": "https://www.last.fm/api/account/create"}

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_MAIN_USER): str,
    }
)


def get_lastfm_user(api_key: str, username: str) -> User:
    """Get lastFM User."""
    return LastFMNetwork(api_key=api_key).get_user(username)


def validate_lastfm_user(user: User) -> dict[str, str]:
    """Return error if the user is not correct. None if it is correct."""
    errors = {}
    try:
        user.get_playcount()
    except WSError as error:
        if error.details == "User not found":
            errors["base"] = "invalid_account"
        elif (
            error.details
            == "Invalid API key - You must be granted a valid key by last.fm"
        ):
            errors["base"] = "invalid_auth"
        else:
            errors["base"] = "unknown"
    except Exception:  # pylint:disable=broad-except
        errors["base"] = "unknown"
    return errors


class LastFmConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for LastFm."""

    data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> LastFmOptionsFlowHandler:
        """Get the options flow for this handler."""
        return LastFmOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize user input."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.data = user_input.copy()
            main_user = get_lastfm_user(
                self.data[CONF_API_KEY], self.data[CONF_MAIN_USER]
            )
            errors = validate_lastfm_user(main_user)
            if not errors:
                return await self.async_step_friends()
        return self.async_show_form(
            step_id="user",
            errors=errors,
            description_placeholders=PLACEHOLDERS,
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
        )

    async def async_step_friends(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Form to select other users and friends."""
        errors = {}
        if user_input is not None:
            valid_users = []
            for username in user_input[CONF_USERS]:
                lastfm_user = get_lastfm_user(self.data[CONF_API_KEY], username)
                lastfm_errors = validate_lastfm_user(lastfm_user)
                if lastfm_errors:
                    errors = lastfm_errors
                else:
                    valid_users.append(username)
            user_input[CONF_USERS] = valid_users
            if not errors:
                return self.async_create_entry(
                    title="LastFM",
                    data={},
                    options={
                        CONF_API_KEY: self.data[CONF_API_KEY],
                        CONF_MAIN_USER: self.data[CONF_MAIN_USER],
                        CONF_USERS: [
                            self.data[CONF_MAIN_USER],
                            *user_input[CONF_USERS],
                        ],
                    },
                )
        try:
            main_user = get_lastfm_user(
                self.data[CONF_API_KEY], self.data[CONF_MAIN_USER]
            )
            friends: Sequence[SelectOptionDict] = [
                {"value": str(friend.name), "label": str(friend.get_name(True))}
                for friend in main_user.get_friends()
            ]
        except WSError:
            friends = []
        return self.async_show_form(
            step_id="friends",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_USERS): SelectSelector(
                            SelectSelectorConfig(
                                options=friends, custom_value=True, multiple=True
                            )
                        ),
                    }
                ),
                user_input or {CONF_USERS: []},
            ),
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import config from yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_API_KEY] == import_config[CONF_API_KEY]:
                return self.async_abort(reason="already_configured")
        return self.async_create_entry(
            title="LastFM",
            data={
                CONF_API_KEY: import_config[CONF_API_KEY],
                CONF_MAIN_USER: None,
                CONF_USERS: import_config[CONF_USERS],
            },
        )


class LastFmOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """LastFm Options flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize form."""
        errors = {}
        if user_input is not None:
            valid_users = []
            for username in user_input[CONF_USERS]:
                lastfm_user = get_lastfm_user(
                    self._config_entry.data[CONF_API_KEY], username
                )
                lastfm_errors = validate_lastfm_user(lastfm_user)
                if lastfm_errors:
                    errors = lastfm_errors
                else:
                    valid_users.append(username)
            user_input[CONF_USERS] = valid_users
            if not errors:
                return self.async_create_entry(
                    title="LastFM",
                    data={
                        **self._config_entry.data,
                        CONF_USERS: user_input[CONF_USERS],
                    },
                )
        if self._config_entry.data[CONF_MAIN_USER]:
            try:
                main_user = get_lastfm_user(
                    self._config_entry.data[CONF_API_KEY],
                    self._config_entry.data[CONF_MAIN_USER],
                )
                friends: Sequence[SelectOptionDict] = [
                    {"value": str(friend.name), "label": str(friend.get_name(True))}
                    for friend in main_user.get_friends()
                ]
            except WSError:
                friends = []
        else:
            friends = []
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_USERS): SelectSelector(
                            SelectSelectorConfig(
                                options=friends, custom_value=True, multiple=True
                            )
                        ),
                    }
                ),
                user_input or self.options,
            ),
        )
