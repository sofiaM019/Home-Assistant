"""Climate platform for Advantage Air integration."""
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_IP_ADDRESS,
    PRECISION_WHOLE,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    TEMP_CELSIUS,
)

from .const import DOMAIN, STATE_CLOSE

ADVANTAGE_AIR_HVAC_MODES = {
    "heat": HVAC_MODE_HEAT,
    "cool": HVAC_MODE_COOL,
    "vent": HVAC_MODE_FAN_ONLY,
    "dry": HVAC_MODE_DRY,
}
HASS_HVAC_MODES = {v: k for k, v in ADVANTAGE_AIR_HVAC_MODES.items()}

ADVANTAGE_AIR_FAN_MODES = {
    "auto": FAN_AUTO,
    "low": FAN_LOW,
    "medium": FAN_MEDIUM,
    "high": FAN_HIGH,
}
HASS_FAN_MODES = {v: k for k, v in ADVANTAGE_AIR_FAN_MODES.items()}
FAN_SPEEDS = {FAN_LOW: 30, FAN_MEDIUM: 60, FAN_HIGH: 100}

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Platform setup isn't required."""
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir climate platform."""

    instance = hass.data[DOMAIN][config_entry.data[CONF_IP_ADDRESS]]

    entities = []
    for _, ac_index in enumerate(instance["coordinator"].data["aircons"]):
        entities.append(AdvantageAirAC(instance, ac_index))
        for _, zone_index in enumerate(
            instance["coordinator"].data["aircons"][ac_index]["zones"]
        ):
            # Only add zone climate control when zone is in temperature control
            if (
                instance["coordinator"].data["aircons"][ac_index]["zones"][zone_index][
                    "type"
                ]
                != 0
            ):
                entities.append(AdvantageAirZone(instance, ac_index, zone_index))
    async_add_entities(entities)
    return True


class AdvantageAirClimateEntity(ClimateEntity):
    """AdvantageAir Climate class."""

    def __init__(self, instance):
        """Initialize the base Advantage Air climate entity."""
        self.coordinator = instance["coordinator"]
        self.async_change = instance["async_change"]
        self.device = instance["device"]

    @property
    def temperature_unit(self):
        """Return the temperature unit."""
        return TEMP_CELSIUS

    @property
    def target_temperature_step(self):
        """Return the supported temperature step."""
        return PRECISION_WHOLE

    @property
    def max_temp(self):
        """Return the maximum supported temperature."""
        return 32

    @property
    def min_temp(self):
        """Return the minimum supported temperature."""
        return 16

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """Return if platform is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return parent device information."""
        return self.device

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Request update."""
        await self.coordinator.async_request_refresh()


class AdvantageAirAC(AdvantageAirClimateEntity):
    """AdvantageAir AC unit."""

    def __init__(self, instance, ac_index):
        """Initialize the Advantage Air AC climate entity."""
        super().__init__(instance)
        self.ac_index = ac_index
        self.aircon = self.coordinator.data["aircons"][self.ac_index]["info"]

    @property
    def name(self):
        """Return the name."""
        return self.aircon["name"]

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_index}-climate'

    @property
    def target_temperature(self):
        """Return the current target temperature."""
        return self.aircon["setTemp"]

    @property
    def hvac_mode(self):
        """Return the current HVAC modes."""
        if self.aircon["state"] == STATE_ON:
            return ADVANTAGE_AIR_HVAC_MODES.get(
                self.aircon["mode"],
                self.aircon["mode"],
            )
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return the supported HVAC modes."""
        return [
            HVAC_MODE_OFF,
            HVAC_MODE_COOL,
            HVAC_MODE_HEAT,
            HVAC_MODE_FAN_ONLY,
            HVAC_MODE_DRY,
        ]

    @property
    def fan_mode(self):
        """Return the current fan modes."""
        return ADVANTAGE_AIR_FAN_MODES.get(self.aircon["fan"], FAN_OFF)

    @property
    def fan_modes(self):
        """Return the supported fan modes."""
        return [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

    @property
    def device_state_attributes(self):
        """Return additional attributes about AC unit."""
        return self.aircon

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the HVAC Mode and State."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.async_change({self.ac_index: {"info": {"state": STATE_OFF}}})
        else:
            await self.async_change(
                {
                    self.ac_index: {
                        "info": {
                            "state": STATE_ON,
                            "mode": HASS_HVAC_MODES.get(hvac_mode),
                        }
                    }
                }
            )

    async def async_set_fan_mode(self, fan_mode):
        """Set the Fan Mode."""
        await self.async_change(
            {self.ac_index: {"info": {"fan": HASS_FAN_MODES.get(fan_mode)}}}
        )

    async def async_set_temperature(self, **kwargs):
        """Set the Temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self.async_change({self.ac_index: {"info": {"setTemp": temp}}})


class AdvantageAirZone(AdvantageAirClimateEntity):
    """AdvantageAir Zone control."""

    def __init__(self, instance, ac_index, zone_index):
        """Initialize the Advantage Air Zone climate entity."""
        super().__init__(instance)
        self.ac_index = ac_index
        self.zone_index = zone_index
        self.zone = self.coordinator.data["aircons"][self.ac_index]["zones"][
            self.zone_index
        ]

    @property
    def name(self):
        """Return the name."""
        return self.coordinator.data["aircons"][self.ac_index]["zones"][
            self.zone_index
        ]["name"]

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_index}-{self.zone_index}-climate'

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.coordinator.data["aircons"][self.ac_index]["zones"][
            self.zone_index
        ]["measuredTemp"]

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self.coordinator.data["aircons"][self.ac_index]["zones"][
            self.zone_index
        ]["setTemp"]

    @property
    def hvac_mode(self):
        """Return the current HVAC modes."""
        if self.zone["state"] == STATE_OPEN:
            return HVAC_MODE_FAN_ONLY
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return supported HVAC modes."""
        return [HVAC_MODE_OFF, HVAC_MODE_FAN_ONLY]

    @property
    def device_state_attributes(self):
        """Return additional attributes about Zone."""
        return self.zone

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the HVAC Mode and State."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.async_change(
                {self.ac_index: {"zones": {self.zone_index: {"state": STATE_CLOSE}}}}
            )
        else:
            await self.async_change(
                {self.ac_index: {"zones": {self.zone_index: {"state": STATE_OPEN}}}}
            )

    async def async_set_temperature(self, **kwargs):
        """Set the Temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self.async_change(
            {self.ac_index: {"zones": {self.zone_index: {"setTemp": temp}}}}
        )
