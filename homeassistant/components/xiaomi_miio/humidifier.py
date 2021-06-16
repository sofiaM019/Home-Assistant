"""Support for Xiaomi Mi Air Purifier and Xiaomi Mi Air Humidifier with humidifier entity."""
from enum import Enum
from functools import partial
import logging
import math

from miio import DeviceException
from miio.airhumidifier import OperationMode as AirhumidifierOperationMode
from miio.airhumidifier_miot import OperationMode as AirhumidifierMiotOperationMode

from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.components.humidifier.const import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DEVICE_CLASS_HUMIDIFIER,
    SUPPORT_MODES,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import ATTR_MODE, CONF_HOST, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.util.percentage import percentage_to_ranged_value

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1,
    MODELS_HUMIDIFIER_MIOT,
    SERVICE_SET_TARGET_HUMIDITY,
)
from .device import XiaomiMiioEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Device"
DATA_KEY = "fan.xiaomi_miio"

CONF_MODEL = "model"

ATTR_MODEL = "model"

# Air Humidifier
ATTR_TARGET_HUMIDITY = "target_humidity"
ATTR_TRANS_LEVEL = "trans_level"
ATTR_HARDWARE_VERSION = "hardware_version"

SUCCESS = ["ok"]

SERVICE_TO_METHOD = {
    SERVICE_SET_TARGET_HUMIDITY: {
        "method": "async_set_target_humidity",
    },
}

AVAILABLE_ATTRIBUTES = {
    ATTR_MODE: "mode",
    ATTR_TARGET_HUMIDITY: "target_humidity",
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import Miio configuration from YAML."""
    _LOGGER.warning(
        "Loading Xiaomi Miio Fan via platform setup is deprecated. "
        "Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fan from a config entry."""
    entities = []

    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        if DATA_KEY not in hass.data:
            hass.data[DATA_KEY] = {}

        host = config_entry.data[CONF_HOST]
        token = config_entry.data[CONF_TOKEN]
        name = config_entry.title
        model = config_entry.data[CONF_MODEL]
        unique_id = config_entry.unique_id

        _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

        if model in MODELS_HUMIDIFIER_MIOT:
            air_humidifier = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
            entity = XiaomiAirHumidifierMiot(
                name,
                air_humidifier,
                config_entry,
                unique_id,
                hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
            )
        else:
            air_humidifier = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
            entity = XiaomiAirHumidifier(
                name,
                air_humidifier,
                config_entry,
                unique_id,
                hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
            )

        hass.data[DATA_KEY][host] = entity
        entities.append(entity)

    async_add_entities(entities, update_before_add=True)


class XiaomiGenericHumidifierDevice(XiaomiMiioEntity, HumidifierEntity):
    """Representation of a generic Xiaomi humidifier device."""

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the generic Xiaomi device."""
        super().__init__(name, device, entry, unique_id, coordinator=coordinator)

        self._available = False
        self._state = None
        self._state_attrs = {ATTR_MODEL: self._model}
        self._skip_update = False
        self._available_modes = []
        self._mode = None
        self._available_attributes = AVAILABLE_ATTRIBUTES
        self._min_humidity = DEFAULT_MIN_HUMIDITY
        self._max_humidity = DEFAULT_MAX_HUMIDITY
        self._humidity_steps = 100

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_HUMIDIFIER

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MODES

    @property
    def should_poll(self):
        """Poll the device."""
        return True

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a miio device command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )

            _LOGGER.debug("Response received from miio device: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            if self._available:
                _LOGGER.error(mask_error, exc)
                self._available = False

            return False

    @property
    def available_modes(self) -> list:
        """Get the list of available modes."""
        return self._available_modes

    @property
    def mode(self):
        """Get the current mode."""
        return self._mode

    @property
    def min_humidity(self):
        """Return the minimum target humidity."""
        return self._min_humidity

    @property
    def max_humidity(self):
        """Return the maximum target humidity."""
        return self._max_humidity

    async def async_turn_on(
        self,
        **kwargs,
    ) -> None:
        """Turn the device on."""
        result = await self._try_command(
            "Turning the miio device on failed.", self._device.on
        )
        await self.coordinator.async_request_refresh()

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        result = await self._try_command(
            "Turning the miio device off failed.", self._device.off
        )
        await self.coordinator.async_request_refresh()

        if result:
            self._state = False
            self._skip_update = True

    async def async_translate_humidity(self, humidity):
        """Translate the target humidity to the first valid step."""
        return (
            math.ceil(percentage_to_ranged_value((1, self._humidity_steps), humidity))
            * 100
            / self._humidity_steps
            if 0 < humidity <= 100
            else None
        )


class XiaomiAirHumidifier(XiaomiGenericHumidifierDevice, HumidifierEntity):
    """Representation of a Xiaomi Air Humidifier."""

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id, coordinator)
        if self._model in [MODEL_AIRHUMIDIFIER_CA1, MODEL_AIRHUMIDIFIER_CB1]:
            self._available_modes = []
            self._available_modes = [
                mode.name
                for mode in AirhumidifierOperationMode
                if mode is not AirhumidifierOperationMode.Strong
            ]
            self._min_humidity = 30
            self._max_humidity = 80
            self._humidity_steps = 10
        elif self._model in [MODEL_AIRHUMIDIFIER_CA4]:
            self._available_modes = [
                mode.name for mode in AirhumidifierMiotOperationMode
            ]
            self._min_humidity = 30
            self._max_humidity = 80
            self._humidity_steps = 100
        else:
            self._available_modes = [
                mode.name
                for mode in AirhumidifierOperationMode
                if mode is not AirhumidifierOperationMode.Auto
            ]
            self._min_humidity = 30
            self._max_humidity = 80
            self._humidity_steps = 10

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )
        self.coordinator.async_add_listener(self.update)

    @callback
    def update(self):
        """Fetch state from the device."""
        state = self.coordinator.data
        if not state:
            return
        _LOGGER.debug("Got new state: %s", state)
        self._available = True
        self._state = state.is_on
        self._state_attrs.update(
            {
                key: self._extract_value_from_attribute(state, value)
                for key, value in self._available_attributes.items()
            }
        )

    @property
    def mode(self):
        """Return the current mode."""
        if self._state:
            return AirhumidifierOperationMode(self._state_attrs[ATTR_MODE]).name

    @property
    def target_humidity(self):
        """Return the target humidity."""
        if self._state:
            return (
                self._state_attrs[ATTR_TARGET_HUMIDITY]
                if AirhumidifierOperationMode(self._state_attrs[ATTR_MODE])
                == AirhumidifierOperationMode.Auto
                else None
            )

    async def async_set_humidity(self, humidity) -> None:
        """Set the target humidity of the humidifier and set the mode to auto."""
        target_humidity = await self.async_translate_humidity(humidity)
        if not target_humidity:
            return

        _LOGGER.debug("Setting the humidity to: %s", target_humidity)
        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_target_humidity,
            target_humidity,
        )
        if (
            self.supported_features & SUPPORT_MODES == 0
            or AirhumidifierOperationMode(self._state_attrs[ATTR_MODE])
            == AirhumidifierOperationMode.Auto
        ):
            return
        _LOGGER.debug("Setting the operation mode to: Auto")
        await self._try_command(
            "Setting operation mode of the miio device to MODE_AUTO failed.",
            self._device.set_mode,
            AirhumidifierOperationMode.Auto,
        )
        await self.coordinator.async_request_refresh()

    async def async_set_mode(self, mode) -> None:
        """Set the mode of the humidifier."""
        if self.supported_features & SUPPORT_MODES == 0 or not mode:
            return

        if mode not in AirhumidifierOperationMode:
            _LOGGER.warning("Mode %s is not a valid operation mode", mode)
            return

        _LOGGER.debug("Setting the operation mode to: %s", mode)
        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            AirhumidifierOperationMode[mode.title()],
        )
        await self.coordinator.async_request_refresh()


class XiaomiAirHumidifierMiot(XiaomiAirHumidifier):
    """Representation of a Xiaomi Air Humidifier (MiOT protocol)."""

    MODE_MAPPING = {
        AirhumidifierMiotOperationMode.Auto: "Auto",
        AirhumidifierMiotOperationMode.Low: "Low",
        AirhumidifierMiotOperationMode.Mid: "Mid",
        AirhumidifierMiotOperationMode.High: "High",
    }

    REVERSE_MODE_MAPPING = {v: k for k, v in MODE_MAPPING.items()}

    @property
    def mode(self):
        """Return the current mode."""
        return AirhumidifierMiotOperationMode(self._state_attrs[ATTR_MODE]).name

    @property
    def target_humidity(self):
        """Return the target humidity."""
        if self._state:
            return (
                self._state_attrs[ATTR_TARGET_HUMIDITY]
                if AirhumidifierMiotOperationMode(self._state_attrs[ATTR_MODE])
                == AirhumidifierMiotOperationMode.Auto
                else None
            )

    async def async_set_humidity(self, humidity) -> None:
        """Set the target humidity of the humidifier and set the mode to auto."""
        target_humidity = await self.async_translate_humidity(humidity)
        if not target_humidity:
            return

        _LOGGER.debug("Setting the humidity to: %s", target_humidity)
        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_target_humidity,
            target_humidity,
        )
        if (
            self.supported_features & SUPPORT_MODES == 0
            or AirhumidifierMiotOperationMode(self._state_attrs[ATTR_MODE])
            == AirhumidifierMiotOperationMode.Auto
        ):
            return
        _LOGGER.debug("Setting the operation mode to: Auto")
        await self._try_command(
            "Setting operation mode of the miio device to MODE_AUTO failed.",
            self._device.set_mode,
            AirhumidifierMiotOperationMode.Auto,
        )
        await self.coordinator.async_request_refresh()

    async def async_set_mode(self, mode) -> None:
        """Set the mode of the fan."""
        if self.supported_features & SUPPORT_MODES == 0 or not mode:
            return

        if mode not in self.REVERSE_MODE_MAPPING:
            _LOGGER.warning("Mode %s is not a valid operation mode", mode)
            return

        _LOGGER.debug("Setting the operation mode to: %s", mode)
        if self._state:
            await self._try_command(
                "Setting operation mode of the miio device failed.",
                self._device.set_mode,
                self.REVERSE_MODE_MAPPING[mode],
            )
        await self.coordinator.async_request_refresh()
