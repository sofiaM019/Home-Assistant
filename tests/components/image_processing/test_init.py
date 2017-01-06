"""The tests for the image_processing component."""
import asyncio
from unittest.mock import patch

from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.bootstrap import setup_component
import homeassistant.components.image_processing as ip

from tests.common import get_test_home_assistant, assert_setup_component


class TestSetupImageProcessing(object):
    """Test class for setup image processing."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Setup demo platfrom on image_process component."""
        config = {
            ip.DOMAIN: {
                'platform': 'demo'
            }
        }

        with assert_setup_component(1, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)

    def test_setup_component_with_service(self):
        """Setup demo platfrom on image_process component test service."""
        config = {
            ip.DOMAIN: {
                'platform': 'demo'
            }
        }

        with assert_setup_component(1, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)

        assert self.hass.services.has_service(ip.DOMAIN, 'scan')


class TestImageProcessing(object):
    """Test class for image processing."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        config = {
            ip.DOMAIN: {
                'platform': 'demo'
            },
            'camera': {
                'platform': 'demo'
            },
        }

        with patch('homeassistant.components.image_processing.demo.'
                   'DemoImageProcessing.should_poll', return_value=False):
            setup_component(self.hass, ip.DOMAIN, config)

        state = self.hass.states.get('camera.demo_camera')
        self.url = "{0}{1}".format(
            self.hass.config.api.base_url,
            state.attributes.get(ATTR_ENTITY_PICTURE))

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.camera.demo.DemoCamera.camera_image',
           autospec=True, return_value=b'Test')
    @patch('homeassistant.components.image_processing.demo.'
           'DemoImageProcessing.process_image', autospec=True)
    def test_get_image_from_camera(self, mock_process, mock_camera):
        """Grab a image from camera entity"""
        self.hass.start()

        ip.scan(self.hass, entity_id='image_processing.demo')
        self.hass.block_till_done()

        assert mock_camera.called
        assert mock_process.called

        assert mock_process.call_args[0][1] == b'Test'

    @patch('homeassistant.components.image_processing.demo.'
           'DemoImageProcessing.process_image', autospec=True)
    def test_get_image_without_exists_camera(self, mock_process):
        """Try to get image without exists camera."""
        self.hass.states.remove('camera.demo_camera')

        ip.scan(self.hass, entity_id='image_processing.demo')
        self.hass.block_till_done()

        assert not mock_process.called

    @patch('homeassistant.components.image_processing.demo.'
           'DemoImageProcessing.process_image', autospec=True)
    def test_get_image_with_timeout(self, mock_process, aioclient_mock):
        """Try to get image with timeout."""
        aioclient_mock.get(self.url, exc=asyncio.TimeoutError())

        ip.scan(self.hass, entity_id='image_processing.demo')
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert not mock_process.called

    @patch('homeassistant.components.image_processing.demo.'
           'DemoImageProcessing.process_image', autospec=True)
    def test_get_image_with_bad_http_state(self, mock_process, aioclient_mock):
        """Try to get image with timeout."""
        aioclient_mock.get(self.url, status=400)

        ip.scan(self.hass, entity_id='image_processing.demo')
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert not mock_process.called
