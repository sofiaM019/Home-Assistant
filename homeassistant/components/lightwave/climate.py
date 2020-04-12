"""Support for LightwaveRF TRVs."""
import logging

from homeassistant.components.climate import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
    ClimateDevice,
)
from homeassistant.components.climate.const import CURRENT_HVAC_HEAT, CURRENT_HVAC_OFF
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    CONF_NAME,
    TEMP_CELSIUS,
)

from . import CONF_SERIAL, LIGHTWAVE_LINK

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Find and return LightWave lights."""
    if not discovery_info:
        return

    trv = []
    lwlink = hass.data[LIGHTWAVE_LINK]

    for device_id, device_config in discovery_info.items():
        name = device_config[CONF_NAME]
        serial = device_config[CONF_SERIAL]
        trv.append(LightwaveTrv(name, device_id, lwlink, serial))

    async_add_entities(trv)


class LightwaveTrv(ClimateDevice):
    """Representation of a LightWaveRF TRV."""

    def __init__(self, name, device_id, lwlink, serial):
        """Initialize LightwaveTrv entity."""
        self._name = name
        self._device_id = device_id
        self._state = None
        self._current_temperature = None
        self._target_temperature = None
        self._target_temperature_step = 0.5
        self._hvac_mode = HVAC_MODE_HEAT
        self._hvac_action = None
        self._lwlink = lwlink
        self._battery = None
        self._serial = serial
        # inhibit is used to prevent race condition on update.  If non zero, skip next update cycle.
        self._inhibit = 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    def update(self):
        """Communicate with a Lightwave RTF Proxy to get state."""
        targ = temp = battery = trv_output = None
        (temp, targ, battery, trv_output) = self._lwlink.read_trv_status(self._serial)
        if temp is not None:
            self._current_temperature = temp
        if targ is not None:
            if self._inhibit == 0:
                self._target_temperature = targ
                if targ == 0:
                    # TRV off
                    self._target_temperature = None
                if targ >= 40:
                    # Call for heat mode, or TRV in a fixed position
                    self._target_temperature = None
            else:
                # Done the job - use proxy next iteration
                self._inhibit = 0
        if battery is not None:
            self._battery = battery
        if trv_output is not None:
            if trv_output > 0:
                self._hvac_action = CURRENT_HVAC_HEAT
            else:
                self._hvac_action = CURRENT_HVAC_OFF

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {
            ATTR_BATTERY_LEVEL: self._battery,
        }

    @property
    def name(self):
        """Lightwave trv name."""
        return self._name

    @property
    def current_temperature(self):
        """Property giving the current room temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Target room temperature."""
        if self._inhibit > 0:
            # if we get an update before the new temp has
            # propagated, the GUI target temp is set back to the
            # old target, showing a false reading temporarily
            self._target_temperature = self._inhibit
        return self._target_temperature

    @property
    def hvac_modes(self):
        """HVAC modes."""
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def hvac_mode(self):
        """HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_action(self):
        """HVAC action."""
        return self._hvac_action

    @property
    def min_temp(self):
        """Min Temp."""
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self):
        """Max Temp."""
        return DEFAULT_MAX_TEMP

    @property
    def temperature_unit(self):
        """Set temperature unit."""
        return TEMP_CELSIUS

    @property
    def target_temperature_step(self):
        """Set temperature step."""
        return self._target_temperature_step

    def set_temperature(self, **kwargs):
        """Set TRV target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._target_temperature = kwargs[ATTR_TEMPERATURE]
            self._inhibit = self._target_temperature
        self._lwlink.set_temperature(
            self._device_id, self._target_temperature, self._name
        )
        self.async_schedule_update_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC Mode for TRV."""
