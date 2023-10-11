"""The tests for the Pilight light platform."""
from __future__ import annotations

import logging

import pytest

import homeassistant.components.light as light
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, mock_component


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "pilight")


async def test_unique_id(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test the setting of value via pilight."""
    caplog.set_level(logging.ERROR)
    with assert_setup_component(1):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "pilight",
                    "lights": {
                        "Light1": {
                            "unique_id": "unique",
                            "on_code": {
                                "protocol": "smartwares_light",
                                "id": "123456",
                                "unit": "1",
                                "on": 1,
                            },
                            "off_code": {
                                "protocol": "light",
                                "id": "123456",
                                "unit": "1",
                                "off": 1,
                            },
                        },
                        "Light2": {
                            "unique_id": "not-so-unique",
                            "on_code": {
                                "protocol": "smartwares_light",
                                "id": "123456",
                                "unit": "2",
                                "on": 1,
                            },
                            "off_code": {
                                "protocol": "smartwares_light",
                                "id": "123456",
                                "unit": "2",
                                "off": 1,
                            },
                        },
                        "Light3": {
                            "unique_id": "not-so-unique",
                            "on_code": {
                                "protocol": "smartwares_light",
                                "id": "123456",
                                "unit": "3",
                                "on": 1,
                            },
                            "off_code": {
                                "protocol": "smartwares_light",
                                "id": "123456",
                                "unit": "3",
                                "off": 1,
                            },
                        },
                    },
                }
            },
        )
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 2

        ent_reg = er.async_get(hass)
        assert len(ent_reg.entities) == 2
        assert ent_reg.async_get_entity_id("light", "pilight", "unique") is not None
        assert (
            ent_reg.async_get_entity_id("light", "pilight", "not-so-unique") is not None
        )
