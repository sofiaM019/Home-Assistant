"""Test squeezebox binary sensors."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FAKE_QUERY_RESPONSE, setup_mocked_integration


async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor states and attributes."""

    # Setup component
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.BINARY_SENSOR],
        ),
        patch(
            "pysqueezebox.Server.async_query",
            return_value=FAKE_QUERY_RESPONSE,
        ),
    ):
        entry = await setup_mocked_integration(hass)
    assert entry is not None

    state = hass.states.get("binary_sensor.fakelib_library_rescan")

    assert state is not None
    assert state.state == "on"
