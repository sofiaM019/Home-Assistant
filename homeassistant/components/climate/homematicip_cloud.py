"""
Support for HomematicIP Cloud climate devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.homematicip_cloud/
"""
import logging

from homeassistant.components.climate import (
    ATTR_TEMPERATURE, STATE_AUTO, STATE_MANUAL, SUPPORT_TARGET_TEMPERATURE,
    ClimateDevice)
from homeassistant.components.homematicip_cloud import (
    HMIPC_HAPID, HomematicipGenericDevice)
from homeassistant.components.homematicip_cloud import DOMAIN as HMIPC_DOMAIN
from homeassistant.const import TEMP_CELSIUS

_LOGGER = logging.getLogger(__name__)

STATE_BOOST = 'Boost'
STATE_PARTY = 'Party'

HMIP_MANUAL = 'MANUAL'

HA_STATE_TO_HMIP = {
    STATE_AUTO: 'AUTOMATIC',
    STATE_MANUAL: 'MANUAL',
}

HMIP_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_HMIP.items()}


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud climate devices."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the HomematicIP climate from a config entry."""
    from homematicip.group import HeatingGroup

    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.groups:
        if isinstance(device, HeatingGroup):
            devices.append(HomematicipHeatingGroup(home, device))

    if devices:
        async_add_entities(devices)


class HomematicipHeatingGroup(HomematicipGenericDevice, ClimateDevice):
    """Representation of a HomematicIP heating group."""

    def __init__(self, home, device):
        """Initialize heating group."""
        device.modelType = 'Group-Heating'
        super().__init__(home, device)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.setPointTemperature

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.actualTemperature

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._device.humidity

    @property
    def current_operation(self):
        """Return current operation ie. automatic or manual."""
        if self._device.boostMode:
            return STATE_BOOST
        elif self._device.partyMode:
            return STATE_PARTY
        elif self._device.controlMode == HMIP_MANUAL:
            return STATE_MANUAL
        return self._device.activeProfile.name

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._device.minTemperature

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._device.maxTemperature

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._device.set_point_temperature(temperature)
