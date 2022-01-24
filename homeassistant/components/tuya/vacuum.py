"""Support for Tuya Vacuums."""
from __future__ import annotations

from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_SEND_COMMAND,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STATUS,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    StateVacuumEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_PAUSED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import EnumTypeData, IntegerTypeData, TuyaEntity
from .const import DOMAIN, LOGGER, TUYA_DISCOVERY_NEW, DPCode, DPType

TUYA_MODE_RETURN_HOME = "chargego"
TUYA_STATUS_TO_HA = {
    "charge_done": STATE_DOCKED,
    "chargecompleted": STATE_DOCKED,
    "charging": STATE_DOCKED,
    "cleaning": STATE_CLEANING,
    "docking": STATE_RETURNING,
    "goto_charge": STATE_RETURNING,
    "goto_pos": STATE_CLEANING,
    "mop_clean": STATE_CLEANING,
    "part_clean": STATE_CLEANING,
    "paused": STATE_PAUSED,
    "pick_zone_clean": STATE_CLEANING,
    "pos_arrived": STATE_CLEANING,
    "pos_unarrive": STATE_CLEANING,
    "sleep": STATE_IDLE,
    "smart_clean": STATE_CLEANING,
    "spot_clean": STATE_CLEANING,
    "standby": STATE_IDLE,
    "wall_clean": STATE_CLEANING,
    "zone_clean": STATE_CLEANING,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya vacuum dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya vacuum."""
        entities: list[TuyaVacuumEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if device.category == "sd":
                entities.append(TuyaVacuumEntity(device, hass_data.device_manager))
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaVacuumEntity(TuyaEntity, StateVacuumEntity):
    """Tuya Vacuum Device."""

    _fan_speed: EnumTypeData | None = None
    _battery_level: IntegerTypeData | None = None
    _supported_features = 0

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager) -> None:
        """Init Tuya vacuum."""
        super().__init__(device, device_manager)

        self._supported_features |= SUPPORT_SEND_COMMAND
        if self.find_dpcode(DPCode.PAUSE, prefer_function=True):
            self._supported_features |= SUPPORT_PAUSE

        if mode := self.find_dpcode(DPCode.MODE, dptype=DPType.ENUM):
            self._supported_features |= SUPPORT_RETURN_HOME
            LOGGER.debug("VACUUM: %s:", mode)
            if TUYA_MODE_RETURN_HOME in mode.range:
                self._supported_features |= SUPPORT_RETURN_HOME

        if self.find_dpcode(DPCode.SEEK, prefer_function=True):
            self._supported_features |= SUPPORT_LOCATE

        if self.find_dpcode(DPCode.STATUS, prefer_function=True):
            self._supported_features |= SUPPORT_STATE | SUPPORT_STATUS

        if self.find_dpcode(DPCode.POWER, prefer_function=True):
            self._supported_features |= SUPPORT_TURN_ON | SUPPORT_TURN_OFF

        if self.find_dpcode(DPCode.POWER_GO, prefer_function=True):
            self._supported_features |= SUPPORT_STOP | SUPPORT_START

        if enum_type := self.find_dpcode(
            DPCode.SUCTION, dptype=DPType.ENUM, prefer_function=True
        ):
            self._supported_features |= SUPPORT_FAN_SPEED
            self._fan_speed = enum_type

        if int_type := self.find_dpcode(DPCode.SUCTION, dptype=DPType.INTEGER):
            self._supported_features |= SUPPORT_BATTERY
            self._battery_level = int_type

    @property
    def battery_level(self) -> int | None:
        """Return Tuya device state."""
        if self._battery_level is None or not (
            status := self.device.status.get(DPCode.ELECTRICITY_LEFT)
        ):
            return None
        return round(self._battery_level.scale_value(status))

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self.device.status.get(DPCode.SUCTION)

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        if self._fan_speed is None:
            return []
        return self._fan_speed.range

    @property
    def state(self) -> str | None:
        """Return Tuya vacuum device state."""
        if self.device.status.get(DPCode.PAUSE) and not (
            self.device.status.get(DPCode.STATUS)
        ):
            return STATE_PAUSED
        if not (status := self.device.status.get(DPCode.STATUS)):
            return None
        return TUYA_STATUS_TO_HA.get(status)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._send_command([{"code": DPCode.POWER, "value": True}])

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._send_command([{"code": DPCode.POWER, "value": False}])

    def start(self, **kwargs: Any) -> None:
        """Start the device."""
        self._send_command([{"code": DPCode.POWER_GO, "value": True}])

    def stop(self, **kwargs: Any) -> None:
        """Stop the device."""
        self._send_command([{"code": DPCode.POWER_GO, "value": False}])

    def pause(self, **kwargs: Any) -> None:
        """Pause the device."""
        self._send_command([{"code": DPCode.POWER_GO, "value": False}])

    def return_to_base(self, **kwargs: Any) -> None:
        """Return device to dock."""
        if self.find_dpcode(DPCode.SWITCH_CHARGE, prefer_function=True):
            self._send_command([{"code": DPCode.SWITCH_CHARGE, "value": True}])
        self._send_command([{"code": DPCode.MODE, "value": TUYA_MODE_RETURN_HOME}])

    def locate(self, **kwargs: Any) -> None:
        """Locate the device."""
        self._send_command([{"code": DPCode.SEEK, "value": True}])

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        self._send_command([{"code": DPCode.SUCTION, "value": fan_speed}])

    def send_command(self, command: str, params: str = None, **kwargs: Any) -> None:
        """Send raw command."""
        if params is None:
            raise ValueError("Params cannot be omitted for Tuya vacuum commands")
        self._send_command([{"code": command, "value": params}])
