"""Platform for switch integration."""
from __future__ import annotations

from dataclasses import dataclass

from boschshcpy import (
    SHCCamera360,
    SHCCameraEyes,
    SHCLightSwitch,
    SHCSession,
    SHCSmartPlug,
    SHCSmartPlugCompact,
)
from boschshcpy.device import SHCDevice

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.helpers.typing import StateType

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity


@dataclass
class SHCSwitchRequiredKeysMixin:
    """Mixin for SHC switch required keys."""

    on_key: str
    on_value: StateType
    has_consumption: bool


@dataclass
class SHCSwitchEntityDescription(
    SwitchEntityDescription,
    SHCSwitchRequiredKeysMixin,
):
    """Class describing SHC switch entities."""


SWITCH_TYPES: dict[str, SHCSwitchEntityDescription] = {
    "smartplug": SHCSwitchEntityDescription(
        key="smartplug",
        device_class=SwitchDeviceClass.OUTLET,
        on_key="state",
        on_value=SHCSmartPlug.PowerSwitchService.State.ON,
        has_consumption=True,
    ),
    "smartplugcompact": SHCSwitchEntityDescription(
        key="smartplugcompact",
        device_class=SwitchDeviceClass.OUTLET,
        on_key="state",
        on_value=SHCSmartPlugCompact.PowerSwitchService.State.ON,
        has_consumption=True,
    ),
    "lightswitch": SHCSwitchEntityDescription(
        key="lightswitch",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="state",
        on_value=SHCLightSwitch.PowerSwitchService.State.ON,
        has_consumption=True,
    ),
    "cameraeyes": SHCSwitchEntityDescription(
        key="cameraeyes",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="cameralight",
        on_value=SHCCameraEyes.CameraLightService.State.ON,
        has_consumption=False,
    ),
    "camera360": SHCSwitchEntityDescription(
        key="camera360",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="privacymode",
        on_value=SHCCamera360.PrivacyModeService.State.DISABLED,
        has_consumption=False,
    ),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the SHC switch platform."""
    entities = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for switch in session.device_helper.smart_plugs:

        entities.append(
            SHCSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["smartplug"],
            )
        )

    for switch in session.device_helper.light_switches:

        entities.append(
            SHCSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["lightswitch"],
            )
        )

    for switch in session.device_helper.smart_plugs_compact:

        entities.append(
            SHCSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["smartplugcompact"],
            )
        )

    for switch in session.device_helper.camera_eyes:

        entities.append(
            SHCCameraSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["cameraeyes"],
            )
        )

    for switch in session.device_helper.camera_360:

        entities.append(
            SHCCameraSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["camera360"],
            )
        )

    if entities:
        async_add_entities(entities)


class SHCSwitch(SHCEntity, SwitchEntity):
    """Representation of a SHC switch."""

    def __init__(
        self,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
        description: SHCSwitchEntityDescription,
    ) -> None:
        """Initialize a SHC switch."""
        super().__init__(device, parent_id, entry_id)
        self.entity_description = description

    @property
    def is_on(self):
        """Return the state of the switch."""
        return (
            getattr(self._device, self.entity_description.on_key)
            == self.entity_description.on_value
        )

    @property
    def today_energy_kwh(self):
        """Return the total energy usage in kWh."""
        if self.entity_description.has_consumption:
            return self._device.energyconsumption / 1000.0
        return None

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        if self.entity_description.has_consumption:
            return self._device.powerconsumption
        return None

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        setattr(self._device, self.entity_description.on_key, True)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        setattr(self._device, self.entity_description.on_key, False)

    def toggle(self, **kwargs):
        """Toggle the switch."""
        setattr(self._device, self.entity_description.on_key, not self.is_on)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.entity_description.key == "smartplug":
            return {
                "routing": self._device.routing.name,
            }
        if self.entity_description.key == "smartplugcompact":
            return {
                "communication_quality": self._device.communicationquality.name,
            }
        return None


class SHCCameraSwitch(SHCSwitch):
    """Representation of a SHC camera switch."""

    @property
    def should_poll(self):
        """Camera needs polling."""
        return True

    def update(self):
        """Trigger an update of the device."""
        self._device.update()
