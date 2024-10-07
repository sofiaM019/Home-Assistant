"""Adds config flow for Mawaqit."""

import logging
import os

from aiohttp.client_exceptions import ClientConnectorError
from mawaqit.consts import NoMosqueAround
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.storage import Store

from . import mawaqit_wrapper, utils
from .const import (
    CONF_CALC_METHOD,
    CONF_SEARCH,
    CONF_TYPE_SEARCH,
    CONF_UUID,
    DOMAIN,
    MAWAQIT_STORAGE_KEY,
    MAWAQIT_STORAGE_VERSION,
)
from .utils import (
    create_data_folder,
    read_all_mosques_NN_file,
    read_my_mosque_NN_file,
    write_all_mosques_NN_file,
    write_my_mosque_NN_file,
)

_LOGGER = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


class MawaqitPrayerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for MAWAQIT."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._errors: dict[str, str] = {}
        self.store: Store | None = None
        self.previous_keyword_search: str = ""

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""

        self._errors = {}

        if self.store is None:
            self.store = Store(self.hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY)

        # lat = self.hass.config.latitude
        # longi = self.hass.config.longitude

        # create data folder if does not exist
        create_data_folder()

        # if the data folder is empty, we can continue the configuration
        # otherwise, we abort the configuration because that means that the user has already configured an entry.
        if await utils.is_another_instance(self.hass, self.store):
            # return self.async_abort(reason="one_instance_allowed")
            return await self.async_step_keep_or_reset()

        if user_input is None:
            return await self._show_config_form(user_input=None)

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        # check if the user credentials are correct (valid = True) :
        try:
            valid = await mawaqit_wrapper.test_credentials(username, password)
        # if we have an error connecting to the server :
        except ClientConnectorError:
            self._errors["base"] = "cannot_connect_to_server"
            return await self._show_config_form(user_input)

        if valid:
            mawaqit_token = await mawaqit_wrapper.get_mawaqit_api_token(
                username, password
            )

            await utils.write_mawaqit_token(self.hass, self.store, mawaqit_token)

            return await self.async_step_search_method()

        self._errors["base"] = "wrong_credential"

        return await self._show_config_form(user_input)

    async def async_step_mosques_coordinates(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle mosques step."""

        self._errors = {}

        lat = self.hass.config.latitude
        longi = self.hass.config.longitude

        mawaqit_token = await utils.read_mawaqit_token(self.hass, self.store)

        if user_input is not None:
            title, data_entry = await utils.async_save_mosque(
                self.hass, self.store, user_input[CONF_UUID], mawaqit_token, lat, longi
            )
            return self.async_create_entry(title=title, data=data_entry)

        return await self._show_config_form2()

    async def async_step_keep_or_reset(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user's choice to keep current data or reset."""
        if user_input is None:
            return await self._show_keep_or_reset_form()

        choice = user_input["choice"]

        if choice == "keep":
            return self.async_abort(reason="configuration_kept")
        if choice == "reset":
            # Clear existing data and restart the configuration process
            await utils.async_clear_data(self.hass, self.store, DOMAIN)
            return await self.async_step_user()
        return await self._show_keep_or_reset_form()

    async def async_step_search_method(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user's choice of search method."""
        if user_input is None:
            return await self._show_search_method_form()

        search_method = user_input[CONF_TYPE_SEARCH]

        mawaqit_token = await utils.read_mawaqit_token(self.hass, self.store)

        if search_method == "coordinates":
            lat = self.hass.config.latitude
            longi = self.hass.config.longitude

            try:
                nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                    lat, longi, token=mawaqit_token
                )
            except NoMosqueAround:
                return self.async_abort(reason="no_mosque")

            await write_all_mosques_NN_file(nearest_mosques, self.store)

            # creation of the list of mosques to be displayed in the options
            name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
                self.store
            )

            await utils.async_write_in_data(
                self.hass, CURRENT_DIR, "mosq_list_data", {"CALC_METHODS": CALC_METHODS}
            )  # TODO deprecate this line and put instead  "await utils.write_mosq_list_data({"CALC_METHODS": CALC_METHODS}, self.store)" # pylint: disable=fixme

            return await self.async_step_mosques_coordinates()

            # return await self._show_config_form2()
        if search_method == "keyword":
            return await self.async_step_keyword_search()

        return await self._show_search_method_form()

    async def async_step_keyword_search(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle the keyword search."""
        if user_input is not None:
            if CONF_SEARCH in user_input:
                keyword = user_input[CONF_SEARCH]

                if keyword == self.previous_keyword_search:
                    if CONF_UUID in user_input:
                        title, data_entry = await utils.async_save_mosque(
                            self.hass,
                            self.store,
                            user_input[CONF_UUID],
                            mawaqit_token=None,
                        )
                        return self.async_create_entry(title=title, data=data_entry)
                else:
                    self.previous_keyword_search = keyword

                mawaqit_token = await utils.read_mawaqit_token(self.hass, self.store)

                result_mosques = await mawaqit_wrapper.all_mosques_by_keyword(
                    search_keyword=keyword, token=mawaqit_token
                )
                await write_all_mosques_NN_file(result_mosques, self.store)

                (
                    name_servers,
                    uuid_servers,
                    CALC_METHODS,
                ) = await read_all_mosques_NN_file(self.store)

                return await self._show_search_keyword_form(user_input, name_servers)

        return await self._show_search_keyword_form(None, None)

    async def _show_search_keyword_form(self, user_input, name_data):
        """Show form to ask the user to choose search method."""
        if user_input is None:
            user_input = {}
            user_input[CONF_SEARCH] = ""

        options = {
            vol.Required(CONF_SEARCH, default=user_input[CONF_SEARCH]): str,
        }

        if name_data is not None:
            options[vol.Required(CONF_UUID)] = vol.In(name_data)

        return self.async_show_form(
            step_id="keyword_search",
            data_schema=vol.Schema(options),
            errors=self._errors,
        )

    async def _show_search_method_form(self):
        """Show form to ask the user to choose search method."""
        options = {
            vol.Required(CONF_TYPE_SEARCH, default="coordinates"): vol.In(
                ["coordinates", "keyword"]
            )
        }

        return self.async_show_form(
            step_id="search_method",
            data_schema=vol.Schema(options),
            errors=self._errors,
        )

    async def _show_config_form(self, user_input):
        if user_input is None:
            user_input = {}
            user_input[CONF_USERNAME] = ""
            user_input[CONF_PASSWORD] = ""

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=user_input[CONF_USERNAME]): str,
                vol.Required(CONF_PASSWORD, default=user_input[CONF_PASSWORD]): str,
            }
        )

        # Show the configuration form to edit location data.
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=self._errors,
        )

    async def _show_config_form2(self):
        """Show the configuration form to edit location data."""
        lat = self.hass.config.latitude
        longi = self.hass.config.longitude

        mawaqit_token = await utils.read_mawaqit_token(self.hass, self.store)

        nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
            lat, longi, token=mawaqit_token
        )

        await write_all_mosques_NN_file(nearest_mosques, self.store)

        name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
            self.store
        )

        return self.async_show_form(
            step_id="mosques_coordinates",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UUID): vol.In(name_servers),
                }
            ),
            errors=self._errors,
        )

    async def _show_keep_or_reset_form(self):
        """Show form to ask the user if they want to keep current data or reset."""
        options = {vol.Required("choice", default="keep"): vol.In(["keep", "reset"])}

        return self.async_show_form(
            step_id="keep_or_reset",
            data_schema=vol.Schema(options),
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return MawaqitPrayerOptionsFlowHandler(config_entry)


class MawaqitPrayerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Mawaqit Prayer client options."""

    def __init__(self, config_entry) -> None:
        """Initialize the options flow handler."""
        self.config_entry = config_entry
        self.store: Store | None = None
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Manage options."""

        self.store = Store(self.hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY)

        if user_input is not None:
            lat = self.hass.config.latitude
            longi = self.hass.config.longitude

            name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
                self.store
            )

            mosque = user_input[CONF_CALC_METHOD]
            index = name_servers.index(mosque)
            mosque_id = uuid_servers[index]

            mawaqit_token = await utils.read_mawaqit_token(self.hass, self.store)

            try:
                nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                    lat, longi, token=mawaqit_token
                )
            except NoMosqueAround as err:
                raise NoMosqueAround("No mosque around.") from err

            await write_my_mosque_NN_file(nearest_mosques[index], self.store)

            await utils.update_my_mosque_data_files(
                self.hass,
                CURRENT_DIR,
                self.store,
                mosque_id=mosque_id,
                token=mawaqit_token,
            )

            title_entry = "MAWAQIT" + " - " + nearest_mosques[index]["name"]

            data_entry = {
                CONF_API_KEY: mawaqit_token,
                CONF_UUID: mosque_id,
                CONF_LATITUDE: lat,
                CONF_LONGITUDE: longi,
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry, title=title_entry, data=data_entry
            )
            # return self.config_entry
            return self.async_create_entry(title=None, data={})

        lat = self.hass.config.latitude
        longi = self.hass.config.longitude

        mawaqit_token = await utils.read_mawaqit_token(self.hass, self.store)

        nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
            lat, longi, token=mawaqit_token
        )

        await write_all_mosques_NN_file(nearest_mosques, self.store)

        name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
            self.store
        )

        current_mosque_data = await read_my_mosque_NN_file(self.store)
        current_mosque = current_mosque_data["uuid"]

        try:
            index = uuid_servers.index(current_mosque)
            default_name = name_servers[index]
        except ValueError:
            default_name = "None"

        options = {
            vol.Required(
                CONF_CALC_METHOD,
                default=default_name,
            ): vol.In(name_servers)
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
