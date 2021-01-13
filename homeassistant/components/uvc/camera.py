"""Support for Ubiquiti's UVC cameras."""
from datetime import datetime
import logging
import re
from typing import Optional

from uvcclient import camera as uvc_camera, nvr
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, SUPPORT_STREAM, Camera
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
)
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_PASSWORD, DEFAULT_PORT, DEFAULT_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_NVR = "nvr"
CONF_KEY = "key"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NVR): cv.string,
        vol.Required(CONF_KEY): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    }
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up UVC integration."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: config["nvr"],
                CONF_API_KEY: config["key"],
                CONF_PASSWORD: config["password"],
                CONF_PORT: config["port"],
                CONF_SSL: config["ssl"],
            },
        )
    )

    return True


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Discover cameras on a Unifi NVR."""

    nvrconn = hass.data[DOMAIN]["nvrconn"]
    cameras = hass.data[DOMAIN]["cameras"]
    identifier = hass.data[DOMAIN]["camera_id_field"]

    async_add_devices(
        [
            UnifiVideoCamera(
                nvrconn,
                camera[identifier],
                camera["name"],
                hass.data[DOMAIN]["camera_password"],
            )
            for camera in cameras
        ],
        True,
    )
    return True


class UnifiVideoCamera(Camera):
    """A Ubiquiti Unifi Video Camera."""

    def __init__(self, camera, uuid, name, password):
        """Initialize an Unifi camera."""
        super().__init__()
        self._nvr = camera
        self._uuid = uuid
        self._name = name
        self._password = password
        self.is_streaming = False
        self._connect_addr = None
        self._camera = None
        self._motion_status = False
        self._caminfo = None

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def should_poll(self):
        """If this entity should be polled."""
        return True

    @property
    def supported_features(self):
        """Return supported features."""
        channels = self._caminfo["channels"]
        for channel in channels:
            if channel["isRtspEnabled"]:
                return SUPPORT_STREAM

        return 0

    @property
    def device_state_attributes(self):
        """Return the camera state attributes."""
        attr = {}
        if self.motion_detection_enabled:
            attr["last_recording_start_time"] = timestamp_ms_to_date(
                self._caminfo["lastRecordingStartTime"]
            )
        return attr

    @property
    def is_recording(self):
        """Return true if the camera is recording."""
        recording_state = "DISABLED"
        if "recordingIndicator" in self._caminfo:
            recording_state = self._caminfo["recordingIndicator"]

        return (
            self._caminfo["recordingSettings"]["fullTimeRecordEnabled"]
            or recording_state == "MOTION_INPROGRESS"
            or recording_state == "MOTION_FINISHED"
        )

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return self._caminfo["recordingSettings"]["motionRecordEnabled"]

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this client."""
        return self._uuid

    @property
    def brand(self):
        """Return the brand of this camera."""
        return "Ubiquiti"

    @property
    def model(self):
        """Return the model of this camera."""
        return self._caminfo["model"]

    def _login(self):
        """Login to the camera."""
        caminfo = self._caminfo
        if self._connect_addr:
            addrs = [self._connect_addr]
        else:
            addrs = [caminfo["host"], caminfo["internalHost"]]

        if self._nvr.server_version >= (3, 2, 0):
            client_cls = uvc_camera.UVCCameraClientV320
        else:
            client_cls = uvc_camera.UVCCameraClient

        if caminfo["username"] is None:
            caminfo["username"] = "ubnt"

        camera = None
        for addr in addrs:
            try:
                camera = client_cls(addr, caminfo["username"], self._password)
                camera.login()
                _LOGGER.debug(
                    "Logged into UVC camera %(name)s via %(addr)s",
                    {"name": self._name, "addr": addr},
                )
                self._connect_addr = addr
                break
            except OSError:
                pass
            except uvc_camera.CameraConnectError:
                pass
            except uvc_camera.CameraAuthError:
                pass
        if not self._connect_addr:
            _LOGGER.error("Unable to login to camera")
            return None

        self._camera = camera
        self._caminfo = caminfo
        return True

    def camera_image(self):
        """Return the image of this camera."""

        if not self._camera:
            if not self._login():
                return

        def _get_image(retry=True):
            try:
                return self._camera.get_snapshot()
            except uvc_camera.CameraConnectError:
                _LOGGER.error("Unable to contact camera")
            except uvc_camera.CameraAuthError:
                if retry:
                    self._login()
                    return _get_image(retry=False)
                _LOGGER.error("Unable to log into camera, unable to get snapshot")
                raise

        return _get_image()

    def set_motion_detection(self, mode):
        """Set motion detection on or off."""
        set_mode = "motion" if mode is True else "none"

        try:
            self._nvr.set_recordmode(self._uuid, set_mode)
            self._motion_status = mode
        except nvr.NvrError as err:
            _LOGGER.error("Unable to set recordmode to %s", set_mode)
            _LOGGER.debug(err)

    def enable_motion_detection(self):
        """Enable motion detection in camlast_recording_start_timeera."""
        self.set_motion_detection(True)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self.set_motion_detection(False)

    async def stream_source(self):
        """Return the source of the stream."""
        for channel in self._caminfo["channels"]:
            if channel["isRtspEnabled"]:
                uri = next(
                    (
                        uri
                        for i, uri in enumerate(channel["rtspUris"])
                        # pylint: disable=protected-access
                        if re.search(self._nvr._host, uri)
                        # pylint: enable=protected-access
                    )
                )
                return uri

        return None

    def update(self):
        """Update the info."""
        self._caminfo = self._nvr.get_camera(self._uuid)


def timestamp_ms_to_date(epoch_ms) -> Optional[datetime]:
    """Convert millisecond timestamp to datetime."""
    if epoch_ms:
        return datetime.fromtimestamp(epoch_ms / 1000)
    return None
