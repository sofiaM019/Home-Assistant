"""Support for Plum Lightpad lights."""
import logging

from plumlightpad import Plum

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.util.color as color_util

from .const import DOMAIN, PLUM_DATA

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Initialize the Plum Lightpad Light and GlowRing."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    plum = Plum(username, password)

    hass.data[DOMAIN][PLUM_DATA] = plum

    def cleanup(event):
        """Clean up resources."""
        plum.cleanup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    cloud_web_sesison = async_get_clientsession(hass, verify_ssl=True)
    await plum.loadCloudData(cloud_web_sesison)

    async def new_lightpad(device):
        """Load light and binary sensor platforms when Lightpad detected."""
        lightpad = plum.get_lightpad(device["lpid"])
        logical_load = lightpad.logical_load
        async_add_entities(
            [
                PlumLightpad(lightpad=lightpad),
                PlumLightpadDimmer(load=logical_load, lightpad=lightpad),
            ]
        )

    device_web_session = async_get_clientsession(hass, verify_ssl=False)
    hass.async_create_task(
        plum.discover(
            hass.loop, lightpadListener=new_lightpad, websession=device_web_session,
        )
    )


class PlumLightpadDimmer(LightEntity):
    """Representation of a Plum Lightpad dimmer."""

    def __init__(self, load, lightpad):
        """Initialize the light."""
        self._load = load
        self._lightpad = lightpad
        self._brightness = load.level
        self._llid = load.llid
        self._name = f"{load.room_name} {load.name}"

    async def async_added_to_hass(self):
        """Subscribe to dimmerchange events."""
        self._load.add_event_listener("dimmerchange", self.dimmerchange)

    def dimmerchange(self, event):
        """Change event handler updating the brightness."""
        self._brightness = event["level"]
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return the ID of this switch."""
        return self._llid + "-" + self._lightpad.config["serialNumber"]

    @property
    def device_info(self):
        """Get device info for Home Assistant."""
        serial_number = self._lightpad.config["serialNumber"]
        info = {
            "identifiers": {(DOMAIN, serial_number)},
            "manufacturer": "Plum",
            "model": "Lightpad",
            "name": f"{self._load.room_name} {self._load.name}",
        }
        return info

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._name

    @property
    def brightness(self) -> int:
        """Return the brightness of this switch between 0..255."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._brightness > 0

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._load.dimmable:
            return SUPPORT_BRIGHTNESS
        return 0

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            await self._load.turn_on(kwargs[ATTR_BRIGHTNESS])
        else:
            await self._load.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._load.turn_off()


class PlumLightpad(LightEntity):
    """Representation of a physical Plum Lightpad w/glow ring."""

    def __init__(self, lightpad):
        """Initialize the light."""
        self._lightpad = lightpad
        self._serial_number = lightpad.config["serialNumber"]
        load = self._lightpad.logical_load
        self._name = f"{load.room_name} {load.name} Glow Ring"

        self._state = lightpad.glow_enabled
        self._glow_intensity = lightpad.glow_intensity

        self._red = lightpad.glow_color["red"]
        self._green = lightpad.glow_color["green"]
        self._blue = lightpad.glow_color["blue"]

    async def async_added_to_hass(self):
        """Subscribe to configchange events."""
        self._lightpad.add_event_listener("configchange", self.configchange_event)

    def configchange_event(self, event):
        """Handle Configuration change event."""
        config = event["changes"]

        self._state = config["glowEnabled"]
        self._glow_intensity = config["glowIntensity"]

        self._red = config["glowColor"]["red"]
        self._green = config["glowColor"]["green"]
        self._blue = config["glowColor"]["blue"]

        self.schedule_update_ha_state()

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return color_util.color_RGB_to_hs(self._red, self._green, self._blue)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return the ID of this switch."""
        return self._serial_number

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._name

    @property
    def device_info(self):
        """Get device info for Home Assistant."""
        load = self._lightpad.logical_load
        info = {
            "identifiers": {(DOMAIN, self._serial_number)},
            "manufacturer": "Plum",
            "model": "Lightpad",
            "name": f"{load.room_name} {load.name}",
        }
        return info

    @property
    def brightness(self) -> int:
        """Return the brightness of this switch between 0..255."""
        return min(max(int(round(self._glow_intensity * 255, 0)), 0), 255)

    @property
    def glow_intensity(self):
        """Brightness in float form."""
        return self._glow_intensity

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    @property
    def icon(self):
        """Return the crop-portrait icon representing the glow ring."""
        return "mdi:crop-portrait"

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness_pct = kwargs[ATTR_BRIGHTNESS] / 255.0
            await self._lightpad.set_config({"glowIntensity": brightness_pct})
        elif ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            red, green, blue = color_util.color_hs_to_RGB(*hs_color)
            await self._lightpad.set_glow_color(red, green, blue, 0)
        else:
            await self._lightpad.set_config({"glowEnabled": True})

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness_pct = kwargs[ATTR_BRIGHTNESS] / 255.0
            await self._lightpad.set_config({"glowIntensity": brightness_pct})
        else:
            await self._lightpad.set_config({"glowEnabled": False})
