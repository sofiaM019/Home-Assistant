"""Test reproduce state for NEW_NAME."""
from homeassistant.core import State

from tests.common import async_mock_service


async def test_reproducing_states(hass):
    """Test reproducing NEW_NAME states."""
    hass.states.async_set("NEW_DOMAIN.entity_off", "off", {})
    hass.states.async_set("NEW_DOMAIN.entity_on", "on", {"color": "red"})

    turn_on_calls = async_mock_service(hass, "NEW_DOMAIN", "turn_on")
    turn_off_calls = async_mock_service(hass, "NEW_DOMAIN", "turn_off")

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("NEW_DOMAIN.entity_off", "off"),
            State("NEW_DOMAIN.entity_on", "on", {"color": "red"}),
        ],
        blocking=True,
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0

    # Make sure correct services are called
    await hass.helpers.state.async_reproduce_state(
        [
            State("NEW_DOMAIN.entity_on", "off"),
            State("NEW_DOMAIN.entity_off", "on", {"color": "red"}),
            # Should not raise
            State("NEW_DOMAIN.non_existing", "on"),
        ],
        blocking=True,
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "NEW_DOMAIN"
    assert turn_on_calls[0].data == {
        "entity_id": "NEW_DOMAIN.entity_off",
        "color": "red",
    }

    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].domain == "NEW_DOMAIN"
    assert turn_off_calls[0].data == {"entity_id": "NEW_DOMAIN.entity_on"}
