"""Support for the Environment Canada radar imagery."""
import asyncio
import datetime

from env_canada import ECRadar
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

ATTR_UPDATED = "updated"

CONF_ATTRIBUTION = "Data provided by Environment Canada"
CONF_STATION = "station"
CONF_LOOP = "loop"
CONF_PRECIP_TYPE = "precip_type"
CONF_RADIUS = "radius"
CONF_RADAR_OPACITY = "radar_opacity"
CONF_LEGEND = "legend"

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_LOOP, default=True): cv.boolean,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_STATION): cv.matches_regex(r"^C[A-Z]{4}$|^[A-Z]{3}$"),
        vol.Inclusive(CONF_LATITUDE, "latlon"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "latlon"): cv.longitude,
        vol.Optional(CONF_PRECIP_TYPE): vol.In(["RAIN", "SNOW"]),
        vol.Optional(CONF_RADIUS, default=200): cv.positive_int,
        vol.Optional(CONF_RADAR_OPACITY, default=65): cv.positive_int,
        vol.Optional(CONF_LEGEND, default=True): cv.boolean,
    }
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Environment Canada camera."""

    kwargs = {
        "precip_type": config.get(CONF_PRECIP_TYPE),
        "radius": config.get(CONF_RADIUS),
        "radar_opacity": config.get(CONF_RADAR_OPACITY),
        "legend": config.get(CONF_LEGEND),
    }

    if config.get(CONF_STATION):
        kwargs["station_id"] = config[CONF_STATION]
    else:
        lat = config.get(CONF_LATITUDE, hass.config.latitude)
        lon = config.get(CONF_LONGITUDE, hass.config.longitude)
        kwargs["coordinates"] = (lat, lon)

    radar_object = ECRadar(**kwargs)

    add_devices(
        [ECCamera(radar_object, config.get(CONF_NAME), config[CONF_LOOP])], True
    )


class ECCamera(Camera):
    """Implementation of an Environment Canada radar camera."""

    def __init__(self, radar_object, camera_name, is_loop):
        """Initialize the camera."""
        super().__init__()

        self.radar_object = radar_object
        self.camera_name = camera_name
        self.is_loop = is_loop
        self.content_type = "image/gif"
        self.image = None
        self.timestamp = None

    def camera_image(self):
        """Return bytes of camera image."""
        self.update()
        return self.image

    @property
    def name(self):
        """Return the name of the camera."""
        if self.camera_name is not None:
            return self.camera_name
        return "Environment Canada Radar"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {ATTR_ATTRIBUTION: CONF_ATTRIBUTION, ATTR_UPDATED: self.timestamp}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update radar image."""
        if self.is_loop:
            self.image = asyncio.run(self.radar_object.get_loop())
        else:
            self.image = asyncio.run(self.radar_object.get_latest_frame())
        self.timestamp = self.radar_object.timestamp
