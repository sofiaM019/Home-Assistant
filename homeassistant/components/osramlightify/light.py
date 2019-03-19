"""
Support for Osram Lightify.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.osramlightify/
"""
import logging
import random
import socket

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_BRIGHTNESS_PCT, ATTR_COLOR_TEMP, ATTR_KELVIN,
    ATTR_HS_COLOR, ATTR_RGB_COLOR, ATTR_XY_COLOR, ATTR_COLOR_NAME,
    ATTR_MIN_MIREDS, ATTR_MAX_MIREDS, ATTR_TRANSITION, ATTR_EFFECT,
    ATTR_EFFECT_LIST, EFFECT_RANDOM, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR, SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_TRANSITION,
    Light)

from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

REQUIREMENTS = ['lightify==1.0.7.1']

_LOGGER = logging.getLogger(__name__)

CONF_ALLOW_LIGHTIFY_NODES = 'allow_lightify_nodes'
CONF_ALLOW_LIGHTIFY_GROUPS = 'allow_lightify_groups'
CONF_INTERVAL_LIGHTIFY_STATUS = 'interval_lightify_status'
CONF_INTERVAL_LIGHTIFY_CONF = 'interval_lightify_conf'

DEFAULT_ALLOW_LIGHTIFY_NODES = True
DEFAULT_ALLOW_LIGHTIFY_GROUPS = True
DEFAULT_INTERVAL_LIGHTIFY_STATUS = 5
DEFAULT_INTERVAL_LIGHTIFY_CONF = 3600

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_ALLOW_LIGHTIFY_NODES,
                 default=DEFAULT_ALLOW_LIGHTIFY_NODES): cv.boolean,
    vol.Optional(CONF_ALLOW_LIGHTIFY_GROUPS,
                 default=DEFAULT_ALLOW_LIGHTIFY_GROUPS): cv.boolean,
    vol.Optional(CONF_INTERVAL_LIGHTIFY_STATUS,
                 default=DEFAULT_INTERVAL_LIGHTIFY_STATUS): cv.positive_int,
    vol.Optional(CONF_INTERVAL_LIGHTIFY_CONF,
                 default=DEFAULT_INTERVAL_LIGHTIFY_CONF): cv.positive_int
})

DEFAULT_BRIGHTNESS = 2
DEFAULT_KELVIN = 2700


def setup_platform(_hass, config, add_entities, _discovery_info=None):
    """Set up the Osram Lightify lights."""
    import lightify

    host = config[CONF_HOST]
    try:
        bridge = lightify.Lightify(host, log_level=logging.NOTSET)
    except socket.error as err:
        msg = "Error connecting to bridge: {} due to: {}".format(
            host, str(err))
        _LOGGER.exception(msg)
        return

    setup_bridge(bridge, add_entities, config)


def setup_bridge(bridge, add_entities, config):
    """Set up the Lightify bridge."""
    lights = {}
    groups = {}
    groups_last_updated = [0]

    def update_lights():
        """Update the lights objects with the latest info from the bridge."""
        try:
            new_lights = bridge.update_all_light_status(
                config[CONF_INTERVAL_LIGHTIFY_STATUS])
            lights_changed = bridge.lights_changed()
        except TimeoutError:
            _LOGGER.error("Timeout during updating of lights")
            return 0
        except OSError:
            _LOGGER.error("OSError during updating of lights")
            return 0

        if new_lights and config[CONF_ALLOW_LIGHTIFY_NODES]:
            new_entities = []
            for addr, light in new_lights.items():
                if addr not in lights:
                    osram_light = OsramLightifyLight(light, update_lights,
                                                     lights_changed)
                    lights[addr] = osram_light
                    new_entities.append(osram_light)
                else:
                    lights[addr].update_luminary(light)

            add_entities(new_entities)

        return lights_changed

    def update_groups():
        """Update the groups objects with the latest info from the bridge."""
        lights_changed = update_lights()

        try:
            new_groups = bridge.update_group_list(
                config[CONF_INTERVAL_LIGHTIFY_CONF])
            groups_updated = bridge.groups_updated()
        except TimeoutError:
            _LOGGER.error("Timeout during updating of groups")
            return 0
        except OSError:
            _LOGGER.error("OSError during updating of groups")
            return 0

        if new_groups:
            new_groups = {group.idx(): group for group in new_groups.values()}
            new_entities = []
            for idx, group in new_groups.items():
                if idx not in groups:
                    osram_group = OsramLightifyGroup(group, update_groups,
                                                     groups_updated)
                    groups[idx] = osram_group
                    new_entities.append(osram_group)
                else:
                    groups[idx].update_luminary(group)

            add_entities(new_entities)

        if groups_updated > groups_last_updated[0]:
            groups_last_updated[0] = groups_updated
            for idx, osram_group in groups.items():
                if idx not in new_groups:
                    osram_group.update_static_attributes()

        return max(lights_changed, groups_updated)

    update_lights()
    if config[CONF_ALLOW_LIGHTIFY_GROUPS]:
        update_groups()


class Luminary(Light):
    """Representation of Luminary Lights and Groups."""

    def __init__(self, luminary, update_func, changed):
        """Initialize a Luminary Light."""
        self.update_func = update_func
        self._luminary = luminary
        self._changed = changed

        self._unique_id = None
        self._supported_features = []
        self._effect_list = []
        self._is_on = False
        self._min_mireds = 0
        self._max_mireds = 0
        self._brightness = 0
        self._color_temp = 0
        self._hs_color = (0, 0)
        self._rgb_color = (0, 0, 0)
        self._xy_color = (0, 0)

        self.update_static_attributes()
        self.update_dynamic_attributes()

    def _get_unique_id(self):
        """Get a unique ID (not implemented)."""
        raise NotImplementedError

    def _get_supported_features(self):
        """Get list of supported features."""
        features = 0
        if 'lum' in self._luminary.supported_features():
            features = features | SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION

        if 'temp' in self._luminary.supported_features():
            features = features | SUPPORT_COLOR_TEMP | SUPPORT_TRANSITION

        if 'rgb' in self._luminary.supported_features():
            features = (features | SUPPORT_COLOR | SUPPORT_TRANSITION |
                        SUPPORT_EFFECT)

        return features

    def _get_effect_list(self):
        """Get list of supported effects."""
        effects = []
        if 'rgb' in self._luminary.supported_features():
            effects.append(EFFECT_RANDOM)

        return effects

    @property
    def name(self):
        """Return the name of the luminary."""
        return self._luminary.name()

    @property
    def hs_color(self):
        """Return last hs color value set."""
        return self._hs_color

    @property
    def color_temp(self):
        """Return the color temperature."""
        return self._color_temp

    @property
    def brightness(self):
        """Return brightness of the luminary (0..255)."""
        return self._brightness

    @property
    def is_on(self):
        """Return True if the device is on."""
        return self._is_on

    @property
    def supported_features(self):
        """List of supported features."""
        return self._supported_features

    @property
    def effect_list(self):
        """List of supported effects."""
        return self._effect_list

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return self._min_mireds

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return self._max_mireds

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def state_attributes(self):
        """Return optional state attributes."""
        data = {}
        if self._supported_features & SUPPORT_COLOR_TEMP:
            data[ATTR_MIN_MIREDS] = self._min_mireds
            data[ATTR_MAX_MIREDS] = self._max_mireds

        if self._supported_features & SUPPORT_EFFECT:
            data[ATTR_EFFECT_LIST] = self._effect_list

        if self.is_on:
            if self._supported_features & SUPPORT_BRIGHTNESS:
                data[ATTR_BRIGHTNESS] = self._brightness

            if self._supported_features & SUPPORT_COLOR_TEMP:
                data[ATTR_COLOR_TEMP] = self._color_temp

            if self._supported_features & SUPPORT_COLOR:
                data[ATTR_RGB_COLOR] = self._rgb_color
                data[ATTR_HS_COLOR] = self._hs_color
                data[ATTR_XY_COLOR] = self._xy_color

        return data

    def play_effect(self, effect, transition):
        """Play selected effect."""
        if effect == EFFECT_RANDOM:
            self._rgb_color = (random.randrange(0, 256),
                               random.randrange(0, 256),
                               random.randrange(0, 256))
            self._hs_color = color_util.color_RGB_to_hs(*self._rgb_color)
            self._xy_color = color_util.color_RGB_to_xy(*self._rgb_color)
            self._luminary.set_rgb(*self._rgb_color, transition)
            self._luminary.set_onoff(True)
            return True

        return False

    def turn_on(self, **kwargs):
        """Turn the device on."""
        transition = int(kwargs.get(ATTR_TRANSITION, 0) * 10)
        if ATTR_EFFECT in kwargs:
            if self.play_effect(kwargs[ATTR_EFFECT], transition):
                self.schedule_update_ha_state()

            return

        if ATTR_HS_COLOR in kwargs:
            self._hs_color = kwargs[ATTR_HS_COLOR]
            self._rgb_color = color_util.color_hs_to_RGB(*self._hs_color)
            self._xy_color = color_util.color_hs_to_xy(*self._hs_color)
            self._luminary.set_rgb(*self._rgb_color, transition)
        elif ATTR_RGB_COLOR in kwargs:
            self._rgb_color = kwargs[ATTR_RGB_COLOR]
            self._hs_color = color_util.color_RGB_to_hs(*self._rgb_color)
            self._xy_color = color_util.color_RGB_to_xy(*self._rgb_color)
            self._luminary.set_rgb(*self._rgb_color, transition)
        elif ATTR_XY_COLOR in kwargs:
            self._xy_color = kwargs[ATTR_XY_COLOR]
            self._rgb_color = color_util.color_xy_to_RGB(*self._xy_color)
            self._xy_color = color_util.color_xy_to_hs(*self._xy_color)
            self._luminary.set_rgb(*self._rgb_color, transition)
        elif ATTR_COLOR_NAME in kwargs:
            self._rgb_color = color_util.color_name_to_rgb(
                kwargs[ATTR_COLOR_NAME])
            self._hs_color = color_util.color_RGB_to_hs(*self._rgb_color)
            self._xy_color = color_util.color_RGB_to_xy(*self._rgb_color)
            self._luminary.set_rgb(*self._rgb_color, transition)

        if ATTR_COLOR_TEMP in kwargs:
            self._color_temp = kwargs[ATTR_COLOR_TEMP]
            self._luminary.set_temperature(
                int(color_util.color_temperature_mired_to_kelvin(
                    self._color_temp)), transition)
        elif ATTR_KELVIN in kwargs:
            self._color_temp = color_util.color_temperature_kelvin_to_mired(
                kwargs[ATTR_KELVIN])
            self._luminary.set_temperature(kwargs[ATTR_KELVIN], transition)

        self._is_on = True
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            self._luminary.set_luminance(int(self._brightness / 2.55),
                                         transition)
        elif ATTR_BRIGHTNESS_PCT in kwargs:
            self._brightness = int(kwargs[ATTR_BRIGHTNESS_PCT] * 2.55)
            self._luminary.set_luminance(int(kwargs[ATTR_BRIGHTNESS_PCT]),
                                         transition)
        else:
            self._luminary.set_onoff(True)

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._is_on = False
        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION] * 10)
            self._brightness = DEFAULT_BRIGHTNESS
            self._luminary.set_luminance(0, transition)
        else:
            self._luminary.set_onoff(False)

        self.schedule_update_ha_state()

    def update_luminary(self, luminary):
        """Update internal luminary object."""
        self._luminary = luminary
        self.update_static_attributes()

    def update_static_attributes(self):
        """Update static attributes of the luminary."""
        self._unique_id = self._get_unique_id()
        self._supported_features = self._get_supported_features()
        self._effect_list = self._get_effect_list()
        if self._supported_features & SUPPORT_COLOR_TEMP:
            self._min_mireds = color_util.color_temperature_kelvin_to_mired(
                self._luminary.max_temp() or DEFAULT_KELVIN)
            self._max_mireds = color_util.color_temperature_kelvin_to_mired(
                self._luminary.min_temp() or DEFAULT_KELVIN)

    def update_dynamic_attributes(self):
        """Update dynamic attributes of the luminary."""
        self._is_on = self._luminary.on()
        if self._supported_features & SUPPORT_BRIGHTNESS:
            self._brightness = int(self._luminary.lum() * 2.55)

        if self._supported_features & SUPPORT_COLOR_TEMP:
            self._color_temp = color_util.color_temperature_kelvin_to_mired(
                self._luminary.temp() or DEFAULT_KELVIN)

        if self._supported_features & SUPPORT_COLOR:
            self._rgb_color = self._luminary.rgb()
            self._hs_color = color_util.color_RGB_to_hs(*self._rgb_color)
            self._xy_color = color_util.color_RGB_to_xy(*self._rgb_color)

    def update(self):
        """Synchronize state with bridge."""
        changed = self.update_func()
        if changed > self._changed:
            self._changed = changed
            self.update_dynamic_attributes()


class OsramLightifyLight(Luminary):
    """Representation of an Osram Lightify Light."""

    def _get_unique_id(self):
        """Get a unique ID."""
        return self._luminary.addr()


class OsramLightifyGroup(Luminary):
    """Representation of an Osram Lightify Group."""

    def _get_unique_id(self):
        """Get a unique ID for the group."""
#       Actually, it's a wrong choice for a unique ID, because a combination of
#       lights is NOT unique (Osram Lightify allows to create different groups
#       with the same lights). Also a combination of lights may easily change,
#       but the group remains the same from the user's perspective.
#       It should be something like "<gateway host>-<group.idx()>"
#       For now keeping it as is for backward compatibility with existing
#       users.
        return '{}'.format(self._luminary.lights())
