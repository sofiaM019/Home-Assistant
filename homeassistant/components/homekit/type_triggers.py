"""Class to hold all sensor accessories."""
import logging

from pyhap.const import CATEGORY_SWITCH

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_NAME,
    CHAR_PROGRAMMABLE_SWITCH_EVENT,
    SERV_STATELESS_PROGRAMMABLE_SWITCH,
)

_LOGGER = logging.getLogger(__name__)


@TYPES.register("DeviceTriggerAccessory")
class DeviceTriggerAccessory(HomeAccessory):
    """Generate a TemperatureSensor accessory for a temperature sensor.

    Sensor entity must return temperature in °C, °F.
    """

    def __init__(self, *args, device_triggers=None, device_id=None):
        """Initialize a TemperatureSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH, device_id=device_id)
        self._triggers = []
        for trigger in device_triggers:
            _LOGGER.warning("Set up up trigger: %s", trigger)
            serv_stateless_switch = self.add_preload_service(
                SERV_STATELESS_PROGRAMMABLE_SWITCH, [CHAR_NAME]
            )
            self._triggers.append(
                serv_stateless_switch.configure_char(
                    CHAR_PROGRAMMABLE_SWITCH_EVENT,
                    value=0,
                    valid_values={"Press": 0},
                )
            )
            type_ = trigger.get("type")
            sub_type = trigger.get("sub_type")
            serv_stateless_switch.configure_char(CHAR_NAME, value=f"{type_} {sub_type}")

    # Attach the trigger using the helper in async run
    # and detach it in async stop
    async def run(self):
        """Handle accessory driver started event."""

    async def stop(self):
        """Handle accessory driver stop event."""
