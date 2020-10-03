"""Tests for 1-Wire device family 1d (DS2423)."""
from unittest.mock import patch

from homeassistant import util
from homeassistant.components.onewire.const import DEFAULT_OWSERVER_PORT
import homeassistant.components.sensor as sensor
from homeassistant.setup import async_setup_component

from tests.common import mock_registry

OWFS_MOUNT_DIR = "/mnt/OneWireTest"

DEVICE_ID = "1D.111111111111"
DEVICE_NAME = "My DS2406"


async def test_setup_owserver(hass):
    """Test setup with OWServer configuration."""
    entity_registry = mock_registry(hass)
    config = {
        "sensor": {
            "platform": "onewire",
            "host": "localhost",
            "port": DEFAULT_OWSERVER_PORT,
            "names": {
                DEVICE_ID: DEVICE_NAME,
            },
        }
    }
    with patch(
        "homeassistant.components.onewire.sensor.protocol.proxy",
    ) as owproxy:
        owproxy.return_value.dir.return_value = [f"/{DEVICE_ID}/"]
        owproxy.return_value.read.side_effect = [
            DEVICE_ID[0:2].encode(),  # read the family
            b"    251123",  # read counter.A
            b"    248125",  # read counter.B
        ]

        assert await async_setup_component(hass, sensor.DOMAIN, config)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == 2

    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_counter_a"
    state = hass.states.get(sensor_id)
    assert state.state == "251123"

    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_counter_b"
    state = hass.states.get(sensor_id)
    assert state.state == "248125"
