"""Provide common fixtures."""
from __future__ import annotations

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pybalboa import SpaControl
from pybalboa.enums import HeatMode, OffLowHighState, OffOnState
import pytest

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry


@pytest.fixture(name="integration")
async def integration_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the balboa integration."""
    return await init_integration(hass)


@pytest.fixture(name="client")
def client_fixture() -> Generator[MagicMock, None, None]:
    """Mock balboa spa client."""
    with patch(
        "homeassistant.components.balboa.SpaClient", autospec=True
    ) as mock_balboa:
        client = mock_balboa.return_value
        callback: list[Callable] = []

        def on(_, _callback: Callable):  # pylint: disable=invalid-name
            callback.append(_callback)
            return lambda: None

        def emit(_):
            for _cb in callback:
                _cb()

        client.on.side_effect = on
        client.emit.side_effect = emit

        client.model = "FakeSpa"
        client.mac_address = "ef:ef:ef:c0:ff:ee"
        client.software_version = "M0 V0.0"

        client.blowers = []
        client.circulation_pump.state = 0
        client.filter_cycle_1_running = False
        client.filter_cycle_2_running = False
        client.temperature_unit = 1
        client.temperature = 10
        client.temperature_minimum = 10
        client.temperature_maximum = 40
        client.target_temperature = 40
        client.heat_mode.state = HeatMode.READY
        client.heat_mode.set_state = AsyncMock()
        client.heat_mode.options = list(HeatMode)[:2]
        client.heat_state = 2

        pump1 = MagicMock(SpaControl)
        pump1.name = "Pump 1"
        pump1.state = OffLowHighState.OFF
        pump1.options = list(OffLowHighState)
        pump1.client = client
        pump1.on.side_effect = on
        pump1.emit.side_effect = emit
        pump2 = MagicMock(SpaControl)
        pump2.name = "Pump 2"
        pump2.state = OffOnState.OFF
        pump2.options = list(OffOnState)
        pump2.client = client
        pump2.on.side_effect = on
        pump2.emit.side_effect = emit
        client.pumps = [pump1, pump2]

        yield client
