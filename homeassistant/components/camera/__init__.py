# pylint: disable=too-many-lines
"""
Component to interface with cameras.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/camera/
"""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.components import bloomsky
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.components.http import HomeAssistantView

DOMAIN = 'camera'
DEPENDENCIES = ['http']
SCAN_INTERVAL = 30
ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    bloomsky.DISCOVER_CAMERAS: 'bloomsky',
}

STATE_RECORDING = 'recording'
STATE_STREAMING = 'streaming'
STATE_IDLE = 'idle'

ENTITY_IMAGE_URL = '/api/camera_proxy/{0}'

MULTIPART_BOUNDARY = '--jpgboundary'
MJPEG_START_HEADER = 'Content-type: {0}\r\n\r\n'


# pylint: disable=too-many-branches
def setup(hass, config):
    """Setup the camera component."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    hass.wsgi.register_view(CameraImageView(hass, component.entities))
    hass.wsgi.register_view(CameraMjpegStream(hass, component.entities))

    component.setup(config)

    return True


class Camera(Entity):
    """The base class for camera entities."""

    def __init__(self):
        """Initialize a camera."""
        self.is_streaming = False

    @property
    def should_poll(self):
        """No need to poll cameras."""
        return False

    @property
    def entity_picture(self):
        """Return a link to the camera feed as entity picture."""
        return ENTITY_IMAGE_URL.format(self.entity_id)

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return False

    @property
    def brand(self):
        """Camera brand."""
        return None

    @property
    def model(self):
        """Camera model."""
        return None

    def camera_image(self):
        """Return bytes of camera image."""
        raise NotImplementedError()

    def mjpeg_stream(self, response):
        """Generate an HTTP MJPEG stream from camera images."""
        import eventlet
        response.mimetype = ('multipart/x-mixed-replace; '
                             'boundary={}'.format(MULTIPART_BOUNDARY))

        boundary = bytes('\r\n{}\r\n'.format(MULTIPART_BOUNDARY), 'utf-8')

        def stream():
            """Stream images as mjpeg stream."""
            try:
                last_image = None
                while True:
                    img_bytes = self.camera_image()

                    if img_bytes is None:
                        continue
                    elif img_bytes == last_image:
                        eventlet.sleep(0.5)

                    yield bytes('Content-length: {}'.format(len(img_bytes)) +
                                '\r\nContent-type: image/jpeg\r\n\r\n',
                                'utf-8')
                    yield img_bytes
                    yield boundary

                    eventlet.sleep(0.5)
            except GeneratorExit:
                pass

        response.response = stream()

        return response

    @property
    def state(self):
        """Camera state."""
        if self.is_recording:
            return STATE_RECORDING
        elif self.is_streaming:
            return STATE_STREAMING
        else:
            return STATE_IDLE

    @property
    def state_attributes(self):
        """Camera state attributes."""
        attr = {}

        if self.model:
            attr['model_name'] = self.model

        if self.brand:
            attr['brand'] = self.brand

        return attr


class CameraView(HomeAssistantView):
    """Base CameraView."""

    def __init__(self, hass, entities):
        """Initialize a basic camera view."""
        super().__init__(hass)
        self.entities = entities


class CameraImageView(CameraView):
    """Camera view to serve an image."""

    url = "/api/camera_proxy/<entity_id>"
    name = "api:camera:image"

    def get(self, request, entity_id):
        """Serve camera image."""
        camera = self.entities.get(entity_id)

        if camera is None:
            return self.Response(status=404)

        response = camera.camera_image()

        if response is None:
            return self.Response(status=500)

        return self.Response(response)


class CameraMjpegStream(CameraView):
    """Camera View to serve an MJPEG stream."""

    url = "/api/camera_proxy_stream/<entity_id>"
    name = "api:camera:stream"

    def get(self, request, entity_id):
        """Serve camera image."""
        camera = self.entities.get(entity_id)

        if camera is None:
            return self.Response(status=404)

        return camera.mjpeg_stream(self.Response())
