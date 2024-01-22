"""Tests for lawn_mower module."""
import logging

import pytest

from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    ("activity", "state", "target_state"),
    [
        ("PARKED_IN_CS", "RESTRICTED", LawnMowerActivity.DOCKED),
        ("UNKNOWN", "PAUSED", LawnMowerActivity.PAUSED),
        ("MOWING", "NOT_APPLICABLE", LawnMowerActivity.MOWING),
        ("NOT_APPLICABLE", "ERROR", LawnMowerActivity.ERROR),
    ],
)
async def test_lawn_mower_states(
    hass: HomeAssistant, setup_entity, activity, state, target_state
) -> None:
    """Test lawn_mower state."""
    state = hass.states.get("lawn_mower.test_mower_1")
    assert state is not None
    assert state.state == target_state


# @pytest.mark.parametrize(
#     ("aioautomower_command", "service"),
#     [
#         ("resume_schedule", "start_mowing"),
#         ("pause_mowing", "pause"),
#         ("park_until_next_schedule", "dock"),
#     ],
# )
# async def test_lawn_mower_commands(
#     hass: HomeAssistant, setup_entity, activity, state, aioautomower_command, service
# ) -> None:
#     """Test lawn_mower commands."""

#     with pytest.raises(HomeAssistantError) as exc_info, patch(
#         f"homeassistant.components.husqvarna_automower.AutomowerSession.{aioautomower_command}",
#         side_effect=ApiException("Test error"),
#     ):
#         await hass.services.async_call(
#             domain="lawn_mower",
#             service=service,
#             service_data={"entity_id": "lawn_mower.test_mower_1"},
#             blocking=True,
#         )
#     assert (
#         str(exc_info.value) == "Command couldn't be sent to the command que: Test error"
#     )
