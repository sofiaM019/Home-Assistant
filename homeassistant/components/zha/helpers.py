"""Helper functions for the ZHA integration."""

from __future__ import annotations

import asyncio
import collections
from collections.abc import Callable
import dataclasses
import enum
import itertools
import logging
import re
import time
from typing import TYPE_CHECKING, Any, NamedTuple

import voluptuous as vol
from zha.application.const import (
    ATTR_DEVICE_IEEE,
    ATTR_TYPE,
    ATTR_UNIQUE_ID,
    CLUSTER_TYPE_IN,
    CLUSTER_TYPE_OUT,
    DATA_ZHA,
    DEVICE_PAIRING_STATUS,
    UNKNOWN_MANUFACTURER,
    UNKNOWN_MODEL,
    ZHA_EVENT,
    ZHA_GW_MSG,
    ZHA_GW_MSG_DEVICE_FULL_INIT,
    ZHA_GW_MSG_DEVICE_INFO,
    ZHA_GW_MSG_DEVICE_JOINED,
    ZHA_GW_MSG_DEVICE_REMOVED,
    ZHA_GW_MSG_GROUP_ADDED,
    ZHA_GW_MSG_GROUP_INFO,
    ZHA_GW_MSG_GROUP_MEMBER_ADDED,
    ZHA_GW_MSG_GROUP_MEMBER_REMOVED,
    ZHA_GW_MSG_GROUP_REMOVED,
    ZHA_GW_MSG_RAW_INIT,
)
from zha.application.gateway import (
    DeviceFullInitEvent,
    DeviceJoinedEvent,
    DeviceLeftEvent,
    DeviceRemovedEvent,
    Gateway,
    GroupEvent,
    RawDeviceInitializedEvent,
)
from zha.application.helpers import ZHAData
from zha.application.platforms import GroupEntity, PlatformEntity
from zha.event import EventBase
from zha.mixins import LogMixin
from zha.zigbee.cluster_handlers import ClusterHandler
from zha.zigbee.device import Device, ZHAEvent
from zha.zigbee.group import Group, GroupMember
from zigpy.application import ControllerApplication
import zigpy.exceptions
from zigpy.profiles import PROFILES
import zigpy.types
from zigpy.types import EUI64
import zigpy.util
import zigpy.zcl
from zigpy.zcl.foundation import CommandSchema

from homeassistant import __path__ as HOMEASSISTANT_PATH
from homeassistant.components.system_log import LogEntry
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, ATTR_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_ACTIVE_COORDINATOR,
    ATTR_AVAILABLE,
    ATTR_DEVICE_TYPE,
    ATTR_ENDPOINT_NAMES,
    ATTR_IEEE,
    ATTR_LAST_SEEN,
    ATTR_LQI,
    ATTR_MANUFACTURER,
    ATTR_MANUFACTURER_CODE,
    ATTR_MODEL,
    ATTR_NEIGHBORS,
    ATTR_NWK,
    ATTR_POWER_SOURCE,
    ATTR_QUIRK_APPLIED,
    ATTR_QUIRK_CLASS,
    ATTR_QUIRK_ID,
    ATTR_ROUTES,
    ATTR_RSSI,
    ATTR_SIGNATURE,
    DOMAIN,
)

if TYPE_CHECKING:
    from logging import Filter, LogRecord

    from .entity import ZHAEntity

    _LogFilterType = Filter | Callable[[LogRecord], bool]

_LOGGER = logging.getLogger(__name__)

DEBUG_COMP_BELLOWS = "bellows"
DEBUG_COMP_ZHA = "homeassistant.components.zha"
DEBUG_LIB_ZHA = "zha"
DEBUG_COMP_ZIGPY = "zigpy"
DEBUG_COMP_ZIGPY_ZNP = "zigpy_znp"
DEBUG_COMP_ZIGPY_DECONZ = "zigpy_deconz"
DEBUG_COMP_ZIGPY_XBEE = "zigpy_xbee"
DEBUG_COMP_ZIGPY_ZIGATE = "zigpy_zigate"
DEBUG_LEVEL_CURRENT = "current"
DEBUG_LEVEL_ORIGINAL = "original"
DEBUG_LEVELS = {
    DEBUG_COMP_BELLOWS: logging.DEBUG,
    DEBUG_COMP_ZHA: logging.DEBUG,
    DEBUG_COMP_ZIGPY: logging.DEBUG,
    DEBUG_COMP_ZIGPY_ZNP: logging.DEBUG,
    DEBUG_COMP_ZIGPY_DECONZ: logging.DEBUG,
    DEBUG_COMP_ZIGPY_XBEE: logging.DEBUG,
    DEBUG_COMP_ZIGPY_ZIGATE: logging.DEBUG,
    DEBUG_LIB_ZHA: logging.DEBUG,
}
DEBUG_RELAY_LOGGERS = [DEBUG_COMP_ZHA, DEBUG_COMP_ZIGPY, DEBUG_LIB_ZHA]
ZHA_GW_MSG_LOG_ENTRY = "log_entry"
ZHA_GW_MSG_LOG_OUTPUT = "log_output"
SIGNAL_REMOVE = "remove"
GROUP_ENTITY_DOMAINS = [Platform.LIGHT, Platform.SWITCH, Platform.FAN]


class GroupEntityReference(NamedTuple):
    """Reference to a group entity."""

    name: str | None
    original_name: str | None
    entity_id: str


class ZHAGroupProxy(LogMixin):
    """Proxy class to interact with the ZHA group instances."""

    def __init__(self, group: Group, gateway_proxy: ZHAGatewayProxy) -> None:
        """Initialize the gateway proxy."""
        self.group: Group = group
        self.gateway_proxy: ZHAGatewayProxy = gateway_proxy

    @property
    def group_info(self) -> dict[str, Any]:
        """Return a group description for group."""
        return {
            "name": self.group.name,
            "group_id": self.group.group_id,
            "members": [
                {
                    "endpoint_id": member.endpoint_id,
                    "device": self.gateway_proxy.device_proxies[
                        member.device.ieee
                    ].zha_device_info,
                    "entities": self.associated_entities(member),
                }
                for member in self.group.members
            ],
        }

    def associated_entities(self, member: GroupMember) -> list[dict[str, Any]]:
        """Return the list of entities that were derived from this endpoint."""
        entity_registry = er.async_get(self.gateway_proxy.hass)
        zha_device_registry: collections.defaultdict[EUI64, list[EntityReference]] = (
            self.gateway_proxy.device_registry
        )

        entity_info = []

        for entity_ref in zha_device_registry.get(member.device.ieee):  # type: ignore[union-attr]
            # We have device entities now that don't leverage cluster handlers
            if not entity_ref.cluster_handlers:
                continue
            entity = entity_registry.async_get(entity_ref.reference_id)
            handler = list(entity_ref.cluster_handlers.values())[0]

            if (
                entity is None
                or handler.cluster.endpoint.endpoint_id != member.endpoint_id
            ):
                continue

            entity_info.append(
                GroupEntityReference(
                    name=entity.name,
                    original_name=entity.original_name,
                    entity_id=entity_ref.reference_id,
                )._asdict()
            )

        return entity_info


class ZHADeviceProxy(EventBase):
    """Proxy class to interact with the ZHA device instances."""

    _ha_device_id: str

    def __init__(self, device: Device, gateway_proxy) -> None:
        """Initialize the gateway proxy."""
        super().__init__()
        self.device: Device = device
        self.gateway_proxy: ZHAGatewayProxy = gateway_proxy
        self._unsubs: list[Callable[[], None]] = []
        self._unsubs.append(self.device.on_all_events(self._handle_event_protocol))

    @property
    def device_id(self) -> str:
        """Return the HA device registry device id."""
        return self._ha_device_id

    @device_id.setter
    def device_id(self, device_id: str) -> None:
        """Set the HA device registry device id."""
        self._ha_device_id = device_id

    @property
    def device_info(self) -> dict[str, Any]:
        """Return a device description for device."""
        ieee = str(self.device.ieee)
        time_struct = time.localtime(self.device.last_seen)
        update_time = time.strftime("%Y-%m-%dT%H:%M:%S", time_struct)
        return {
            ATTR_IEEE: ieee,
            ATTR_NWK: self.device.nwk,
            ATTR_MANUFACTURER: self.device.manufacturer,
            ATTR_MODEL: self.device.model,
            ATTR_NAME: self.device.name or ieee,
            ATTR_QUIRK_APPLIED: self.device.quirk_applied,
            ATTR_QUIRK_CLASS: self.device.quirk_class,
            ATTR_QUIRK_ID: self.device.quirk_id,
            ATTR_MANUFACTURER_CODE: self.device.manufacturer_code,
            ATTR_POWER_SOURCE: self.device.power_source,
            ATTR_LQI: self.device.lqi,
            ATTR_RSSI: self.device.rssi,
            ATTR_LAST_SEEN: update_time,
            ATTR_AVAILABLE: self.device.available,
            ATTR_DEVICE_TYPE: self.device.device_type,
            ATTR_SIGNATURE: self.device.zigbee_signature,
        }

    @property
    def zha_device_info(self) -> dict[str, Any]:
        """Get ZHA device information."""
        device_info: dict[str, Any] = {}
        device_info.update(self.device_info)
        device_info[ATTR_ACTIVE_COORDINATOR] = self.device.is_active_coordinator
        device_info["entities"] = [
            {
                "entity_id": entity_ref.reference_id,
                ATTR_NAME: entity_ref.device_info[ATTR_NAME],
            }
            for entity_ref in self.gateway_proxy.device_registry[self.device.ieee]
        ]

        topology = self.gateway_proxy.gateway.application_controller.topology
        device_info[ATTR_NEIGHBORS] = [
            {
                "device_type": neighbor.device_type.name,
                "rx_on_when_idle": neighbor.rx_on_when_idle.name,
                "relationship": neighbor.relationship.name,
                "extended_pan_id": str(neighbor.extended_pan_id),
                "ieee": str(neighbor.ieee),
                "nwk": str(neighbor.nwk),
                "permit_joining": neighbor.permit_joining.name,
                "depth": str(neighbor.depth),
                "lqi": str(neighbor.lqi),
            }
            for neighbor in topology.neighbors[self.device.ieee]
        ]

        device_info[ATTR_ROUTES] = [
            {
                "dest_nwk": str(route.DstNWK),
                "route_status": str(route.RouteStatus.name),
                "memory_constrained": bool(route.MemoryConstrained),
                "many_to_one": bool(route.ManyToOne),
                "route_record_required": bool(route.RouteRecordRequired),
                "next_hop": str(route.NextHop),
            }
            for route in topology.routes[self.device.ieee]
        ]

        # Return endpoint device type Names
        names: list[dict[str, str]] = []
        for endpoint in (
            ep for epid, ep in self.device.device.endpoints.items() if epid
        ):
            profile = PROFILES.get(endpoint.profile_id)
            if profile and endpoint.device_type is not None:
                # DeviceType provides undefined enums
                names.append({ATTR_NAME: profile.DeviceType(endpoint.device_type).name})
            else:
                names.append(
                    {
                        ATTR_NAME: (
                            f"unknown {endpoint.device_type} device_type "
                            f"of 0x{(endpoint.profile_id or 0xFFFF):04x} profile id"
                        )
                    }
                )
        device_info[ATTR_ENDPOINT_NAMES] = names

        device_registry = dr.async_get(self.gateway_proxy.hass)
        reg_device = device_registry.async_get(self.device_id)
        if reg_device is not None:
            device_info["user_given_name"] = reg_device.name_by_user
            device_info["device_reg_id"] = reg_device.id
            device_info["area_id"] = reg_device.area_id
        return device_info

    def handle_zha_event(self, zha_event: ZHAEvent) -> None:
        """Handle a ZHA event."""
        self.gateway_proxy.hass.bus.async_fire(
            ZHA_EVENT,
            {
                ATTR_DEVICE_IEEE: zha_event.device_ieee,
                ATTR_UNIQUE_ID: zha_event.unique_id,
                ATTR_DEVICE_ID: self.device_id,
                **zha_event.data,
            },
        )


class EntityReference(NamedTuple):
    """Describes an entity reference."""

    reference_id: str
    zha_device: ZHADeviceProxy
    cluster_handlers: dict[str, ClusterHandler]
    device_info: dr.DeviceInfo
    remove_future: asyncio.Future[Any]


class ZHAGatewayProxy(EventBase):
    """Proxy class to interact with the ZHA gateway."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, gateway: Gateway
    ) -> None:
        """Initialize the gateway proxy."""
        super().__init__()
        self.hass = hass
        self.config_entry = config_entry
        self.gateway: Gateway = gateway
        self.device_proxies: dict[str, ZHADeviceProxy] = {}
        self.group_proxies: dict[int, ZHAGroupProxy] = {}
        self._device_registry: collections.defaultdict[EUI64, list[EntityReference]] = (
            collections.defaultdict(list)
        )
        self._log_levels: dict[str, dict[str, int]] = {
            DEBUG_LEVEL_ORIGINAL: async_capture_log_levels(),
            DEBUG_LEVEL_CURRENT: async_capture_log_levels(),
        }
        self.debug_enabled: bool = False
        self._log_relay_handler: LogRelayHandler = LogRelayHandler(hass, self)
        self._unsubs: list[Callable[[], None]] = []
        self._unsubs.append(self.gateway.on_all_events(self._handle_event_protocol))

    @property
    def device_registry(self) -> collections.defaultdict[EUI64, list[EntityReference]]:
        """Return entities by ieee."""
        return self._device_registry

    def register_entity_reference(
        self,
        ieee: EUI64,
        reference_id: str,
        zha_device: ZHADeviceProxy,
        cluster_handlers: dict[str, ClusterHandler],
        device_info: dr.DeviceInfo,
        remove_future: asyncio.Future[Any],
    ):
        """Record the creation of a hass entity associated with ieee."""
        self._device_registry[ieee].append(
            EntityReference(
                reference_id=reference_id,
                zha_device=zha_device,
                cluster_handlers=cluster_handlers,
                device_info=device_info,
                remove_future=remove_future,
            )
        )

    async def async_initialize_devices_and_entities(self) -> None:
        """Initialize devices and entities."""
        ha_zha_data = get_zha_data(self.hass)
        for device in self.gateway.devices.values():
            device_proxy = self._async_get_or_create_device_proxy(device)
            self.device_proxies[device.ieee] = device_proxy
            for entity in device.platform_entities.values():
                platform = Platform(entity.PLATFORM)
                ha_zha_data.platforms[platform].append(
                    EntityData(entity=entity, device_proxy=device_proxy)
                )
        for group in self.gateway.groups.values():
            group_proxy = self._async_get_or_create_group_proxy(group)
            self.group_proxies[group.group_id] = group_proxy
            for entity in group.group_entities.values():
                platform = Platform(entity.PLATFORM)
                ha_zha_data.platforms[platform].append(
                    EntityData(
                        entity=entity,
                        device_proxy=self.device_proxies[
                            self.gateway.coordinator_zha_device.ieee
                        ],
                    )
                )

        await self.gateway.async_initialize_devices_and_entities()

    def handle_device_joined(self, event: DeviceJoinedEvent) -> None:
        """Handle a device joined event."""
        self._async_get_or_create_device_proxy(event.device_info)
        async_dispatcher_send(
            self.hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: ZHA_GW_MSG_DEVICE_JOINED,
                ZHA_GW_MSG_DEVICE_INFO: {
                    ATTR_NWK: event.device_info.nwk,
                    ATTR_IEEE: str(event.device_info.ieee),
                    DEVICE_PAIRING_STATUS: event.device_info.pairing_status.name,
                },
            },
        )

    def handle_device_removed(self, event: DeviceRemovedEvent) -> None:
        """Handle a device removed event."""
        zha_device_proxy = self.device_proxies.pop(event.device_info.ieee, None)
        entity_refs = self._device_registry.pop(event.device_info.ieee, None)
        if zha_device_proxy is not None:
            device_info = zha_device_proxy.zha_device_info
            # zha_device_proxy.async_cleanup_handles()
            async_dispatcher_send(
                self.hass, f"{SIGNAL_REMOVE}_{str(zha_device_proxy.device.ieee)}"
            )
            self.hass.async_create_task(
                self._async_remove_device(zha_device_proxy, entity_refs),
                "ZHAGateway._async_remove_device",
            )
            if device_info is not None:
                async_dispatcher_send(
                    self.hass,
                    ZHA_GW_MSG,
                    {
                        ATTR_TYPE: ZHA_GW_MSG_DEVICE_REMOVED,
                        ZHA_GW_MSG_DEVICE_INFO: device_info,
                    },
                )

    def handle_device_left(self, event: DeviceLeftEvent) -> None:
        """Handle a device left event."""

    def handle_raw_device_initialized(self, event: RawDeviceInitializedEvent) -> None:
        """Handle a raw device initialized event."""
        manuf = event.device_info.manufacturer
        async_dispatcher_send(
            self.hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: ZHA_GW_MSG_RAW_INIT,
                ZHA_GW_MSG_DEVICE_INFO: {
                    ATTR_NWK: event.device_info.nwk,
                    ATTR_IEEE: str(event.device_info.ieee),
                    DEVICE_PAIRING_STATUS: event.device_info.pairing_status.name,
                    ATTR_MODEL: event.device_info.model
                    if event.device_info.model
                    else UNKNOWN_MODEL,
                    ATTR_MANUFACTURER: manuf if manuf else UNKNOWN_MANUFACTURER,
                    ATTR_SIGNATURE: event.device_info.signature,
                },
            },
        )

    def handle_device_fully_initialized(self, event: DeviceFullInitEvent) -> None:
        """Handle a device fully initialized event."""
        zha_device_proxy = self.device_proxies[event.device_info.ieee]
        device_info = zha_device_proxy.zha_device_info
        device_info[DEVICE_PAIRING_STATUS] = event.device_info.pairing_status.name
        async_dispatcher_send(
            self.hass,
            ZHA_GW_MSG,
            {
                ATTR_TYPE: ZHA_GW_MSG_DEVICE_FULL_INIT,
                ZHA_GW_MSG_DEVICE_INFO: device_info,
            },
        )

    def handle_group_member_removed(self, event: GroupEvent) -> None:
        """Handle a group member removed event."""
        zha_group_proxy = self._async_get_or_create_group_proxy(event.group_info)
        zha_group_proxy.info("group_member_removed - group_info: %s", event.group_info)
        self._send_group_gateway_message(
            zha_group_proxy, ZHA_GW_MSG_GROUP_MEMBER_REMOVED
        )

    def handle_group_member_added(self, event: GroupEvent) -> None:
        """Handle a group member added event."""
        zha_group_proxy = self._async_get_or_create_group_proxy(event.group_info)
        zha_group_proxy.info("group_member_added - group_info: %s", event.group_info)
        self._send_group_gateway_message(zha_group_proxy, ZHA_GW_MSG_GROUP_MEMBER_ADDED)
        # if len(zha_group_proxy.members) == 2:
        # we need to do this because there wasn't already
        # a group entity to remove and re-add
        # discovery.GROUP_PROBE.discover_group_entities(zha_group)

    def handle_group_added(self, event: GroupEvent) -> None:
        """Handle a group added event."""
        zha_group_proxy = self._async_get_or_create_group_proxy(event.group_info)
        zha_group_proxy.info("group_added")
        # need to dispatch for entity creation here
        self._send_group_gateway_message(zha_group_proxy, ZHA_GW_MSG_GROUP_ADDED)

    def handle_group_removed(self, event: GroupEvent) -> None:
        """Handle a group removed event."""
        self._send_group_gateway_message(event.group_info, ZHA_GW_MSG_GROUP_REMOVED)
        zha_group_proxy = self._groups.pop(event.group_info.group_id)
        zha_group_proxy.info("group_removed")
        self._cleanup_group_entity_registry_entries(zha_group_proxy)

    def _send_group_gateway_message(
        self, zigpy_group: zigpy.group.Group, gateway_message_type: str
    ) -> None:
        """Send the gateway event for a zigpy group event."""
        zha_group = self._groups.get(zigpy_group.group_id)
        if zha_group is not None:
            async_dispatcher_send(
                self.hass,
                ZHA_GW_MSG,
                {
                    ATTR_TYPE: gateway_message_type,
                    ZHA_GW_MSG_GROUP_INFO: zha_group.group_info,
                },
            )

    async def _async_remove_device(
        self, device: ZHADeviceProxy, entity_refs: list[EntityReference] | None
    ) -> None:
        if entity_refs is not None:
            remove_tasks: list[asyncio.Future[Any]] = [
                entity_ref.remove_future for entity_ref in entity_refs
            ]
            if remove_tasks:
                await asyncio.wait(remove_tasks)

        device_registry = dr.async_get(self.hass)
        reg_device = device_registry.async_get(device.device_id)
        if reg_device is not None:
            device_registry.async_remove_device(reg_device.id)

    @callback
    def async_enable_debug_mode(self, filterer: _LogFilterType | None = None) -> None:
        """Enable debug mode for ZHA."""
        self._log_levels[DEBUG_LEVEL_ORIGINAL] = async_capture_log_levels()
        async_set_logger_levels(DEBUG_LEVELS)
        self._log_levels[DEBUG_LEVEL_CURRENT] = async_capture_log_levels()

        if filterer:
            self._log_relay_handler.addFilter(filterer)

        for logger_name in DEBUG_RELAY_LOGGERS:
            logging.getLogger(logger_name).addHandler(self._log_relay_handler)

        self.debug_enabled = True

    @callback
    def async_disable_debug_mode(self, filterer: _LogFilterType | None = None) -> None:
        """Disable debug mode for ZHA."""
        async_set_logger_levels(self._log_levels[DEBUG_LEVEL_ORIGINAL])
        self._log_levels[DEBUG_LEVEL_CURRENT] = async_capture_log_levels()
        for logger_name in DEBUG_RELAY_LOGGERS:
            logging.getLogger(logger_name).removeHandler(self._log_relay_handler)
        if filterer:
            self._log_relay_handler.removeFilter(filterer)
        self.debug_enabled = False

    async def shutdown(self) -> None:
        """Shutdown the gateway proxy."""
        for unsub in self._unsubs:
            unsub()
        await self.gateway.shutdown()

    @callback
    def _async_get_or_create_device_proxy(self, zha_device: Device) -> ZHADeviceProxy:
        """Get or create a ZHA device."""
        if (zha_device_proxy := self.device_proxies.get(zha_device.ieee)) is None:
            zha_device_proxy = ZHADeviceProxy(zha_device, self)
            self.device_proxies[zha_device_proxy.device.ieee] = zha_device_proxy

            device_registry = dr.async_get(self.hass)
            device_registry_device = device_registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                connections={(dr.CONNECTION_ZIGBEE, str(zha_device.ieee))},
                identifiers={(DOMAIN, str(zha_device.ieee))},
                name=zha_device.name,
                manufacturer=zha_device.manufacturer,
                model=zha_device.model,
            )
            zha_device_proxy.device_id = device_registry_device.id
        return zha_device_proxy

    @callback
    def _async_get_or_create_group_proxy(self, zha_group: Group) -> ZHAGroupProxy:
        """Get or create a ZHA group."""
        zha_group_proxy = self.group_proxies.get(zha_group.group_id)
        if zha_group_proxy is None:
            zha_group_proxy = ZHAGroupProxy(zha_group, self)
            self.group_proxies[zha_group.group_id] = zha_group_proxy
        return zha_group_proxy

    def get_device_proxy(self, ieee: EUI64) -> ZHADeviceProxy | None:
        """Return ZHADevice for given ieee."""
        return self._devices.get(ieee)

    def get_group_proxy(self, group_id: int | str) -> ZHAGroupProxy | None:
        """Return Group for given group id."""
        if isinstance(group_id, str):
            for group in self.groups.values():
                if group.name == group_id:
                    return group
            return None
        return self.groups.get(group_id)

    def get_entity_reference(self, entity_id: str) -> EntityReference | None:
        """Return entity reference for given entity_id if found."""
        for entity_reference in itertools.chain.from_iterable(
            self.device_registry.values()
        ):
            if entity_id == entity_reference.reference_id:
                return entity_reference
        return None

    def remove_entity_reference(self, entity: ZHAEntity) -> None:
        """Remove entity reference for given entity_id if found."""
        if entity.zha_device.ieee in self.device_registry:
            entity_refs = self.device_registry.get(entity.zha_device.ieee)
            self.device_registry[entity.zha_device.ieee] = [
                e
                for e in entity_refs  # type: ignore[union-attr]
                if e.reference_id != entity.entity_id
            ]

    def _cleanup_group_entity_registry_entries(
        self, zigpy_group: zigpy.group.Group
    ) -> None:
        """Remove entity registry entries for group entities when the groups are removed from HA."""
        # first we collect the potential unique ids for entities that could be created from this group
        possible_entity_unique_ids = [
            f"{domain}_zha_group_0x{zigpy_group.group_id:04x}"
            for domain in GROUP_ENTITY_DOMAINS
        ]

        # then we get all group entity entries tied to the coordinator
        entity_registry = er.async_get(self.hass)
        assert self.coordinator_zha_device
        all_group_entity_entries = er.async_entries_for_device(
            entity_registry,
            self.coordinator_zha_device.device_id,
            include_disabled_entities=True,
        )

        # then we get the entity entries for this specific group
        # by getting the entries that match
        entries_to_remove = [
            entry
            for entry in all_group_entity_entries
            if entry.unique_id in possible_entity_unique_ids
        ]

        # then we remove the entries from the entity registry
        for entry in entries_to_remove:
            _LOGGER.debug(
                "cleaning up entity registry entry for entity: %s", entry.entity_id
            )
            entity_registry.async_remove(entry.entity_id)


class ZHAFirmwareUpdateCoordinator(DataUpdateCoordinator[None]):  # pylint: disable=hass-enforce-coordinator-module
    """Firmware update coordinator that broadcasts updates network-wide."""

    def __init__(
        self, hass: HomeAssistant, controller_application: ControllerApplication
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ZHA firmware update coordinator",
            update_method=self.async_update_data,
        )
        self.controller_application = controller_application

    async def async_update_data(self) -> None:
        """Fetch the latest firmware update data."""
        # Broadcast to all devices
        await self.controller_application.ota.broadcast_notify(jitter=100)


@callback
def async_capture_log_levels() -> dict[str, int]:
    """Capture current logger levels for ZHA."""
    return {
        DEBUG_COMP_BELLOWS: logging.getLogger(DEBUG_COMP_BELLOWS).getEffectiveLevel(),
        DEBUG_COMP_ZHA: logging.getLogger(DEBUG_COMP_ZHA).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY: logging.getLogger(DEBUG_COMP_ZIGPY).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_ZNP: logging.getLogger(
            DEBUG_COMP_ZIGPY_ZNP
        ).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_DECONZ: logging.getLogger(
            DEBUG_COMP_ZIGPY_DECONZ
        ).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_XBEE: logging.getLogger(
            DEBUG_COMP_ZIGPY_XBEE
        ).getEffectiveLevel(),
        DEBUG_COMP_ZIGPY_ZIGATE: logging.getLogger(
            DEBUG_COMP_ZIGPY_ZIGATE
        ).getEffectiveLevel(),
        DEBUG_LIB_ZHA: logging.getLogger(DEBUG_LIB_ZHA).getEffectiveLevel(),
    }


@callback
def async_set_logger_levels(levels: dict[str, int]) -> None:
    """Set logger levels for ZHA."""
    logging.getLogger(DEBUG_COMP_BELLOWS).setLevel(levels[DEBUG_COMP_BELLOWS])
    logging.getLogger(DEBUG_COMP_ZHA).setLevel(levels[DEBUG_COMP_ZHA])
    logging.getLogger(DEBUG_COMP_ZIGPY).setLevel(levels[DEBUG_COMP_ZIGPY])
    logging.getLogger(DEBUG_COMP_ZIGPY_ZNP).setLevel(levels[DEBUG_COMP_ZIGPY_ZNP])
    logging.getLogger(DEBUG_COMP_ZIGPY_DECONZ).setLevel(levels[DEBUG_COMP_ZIGPY_DECONZ])
    logging.getLogger(DEBUG_COMP_ZIGPY_XBEE).setLevel(levels[DEBUG_COMP_ZIGPY_XBEE])
    logging.getLogger(DEBUG_COMP_ZIGPY_ZIGATE).setLevel(levels[DEBUG_COMP_ZIGPY_ZIGATE])
    logging.getLogger(DEBUG_LIB_ZHA).setLevel(levels[DEBUG_LIB_ZHA])


class LogRelayHandler(logging.Handler):
    """Log handler for error messages."""

    def __init__(self, hass: HomeAssistant, gateway: ZHAGatewayProxy) -> None:
        """Initialize a new LogErrorHandler."""
        super().__init__()
        self.hass = hass
        self.gateway = gateway
        hass_path: str = HOMEASSISTANT_PATH[0]
        config_dir = self.hass.config.config_dir
        self.paths_re = re.compile(
            r"(?:{})/(.*)".format(
                "|".join([re.escape(x) for x in (hass_path, config_dir)])
            )
        )

    def emit(self, record: LogRecord) -> None:
        """Relay log message via dispatcher."""
        entry = LogEntry(
            record, self.paths_re, figure_out_source=record.levelno >= logging.WARNING
        )
        async_dispatcher_send(
            self.hass,
            ZHA_GW_MSG,
            {ATTR_TYPE: ZHA_GW_MSG_LOG_OUTPUT, ZHA_GW_MSG_LOG_ENTRY: entry.to_dict()},
        )


@dataclasses.dataclass(kw_only=True, slots=True)
class HAZHAData:
    """ZHA data stored in `hass.data`."""

    data: ZHAData
    gateway_proxy: ZHAGatewayProxy | None = dataclasses.field(default=None)
    platforms: collections.defaultdict[Platform, list] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(list)
    )
    update_coordinator: ZHAFirmwareUpdateCoordinator | None = dataclasses.field(
        default=None
    )


@dataclasses.dataclass(kw_only=True, slots=True)
class EntityData:
    """ZHA entity data."""

    entity: PlatformEntity | GroupEntity
    device_proxy: ZHADeviceProxy


def get_zha_data(hass: HomeAssistant) -> HAZHAData:
    """Get the global ZHA data object."""
    if DATA_ZHA not in hass.data:
        hass.data[DATA_ZHA] = HAZHAData(data=ZHAData())

    return hass.data[DATA_ZHA]


def get_zha_gateway(hass: HomeAssistant) -> Gateway:
    """Get the ZHA gateway object."""
    if (gateway_proxy := get_zha_data(hass).gateway_proxy) is None:
        raise ValueError("No gateway object exists")

    return gateway_proxy.gateway


def get_zha_gateway_proxy(hass: HomeAssistant) -> ZHAGatewayProxy:
    """Get the ZHA gateway object."""
    if (gateway_proxy := get_zha_data(hass).gateway_proxy) is None:
        raise ValueError("No gateway object exists")

    return gateway_proxy


def get_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Get the ZHA gateway object."""
    if (gateway_proxy := get_zha_data(hass).gateway_proxy) is None:
        raise ValueError("No gateway object exists to retrieve the config entry from.")

    return gateway_proxy.config_entry


@callback
def async_get_zha_device_proxy(hass: HomeAssistant, device_id: str) -> ZHADeviceProxy:
    """Get a ZHA device for the given device registry id."""
    device_registry = dr.async_get(hass)
    registry_device = device_registry.async_get(device_id)
    if not registry_device:
        _LOGGER.error("Device id `%s` not found in registry", device_id)
        raise KeyError(f"Device id `{device_id}` not found in registry.")
    zha_gateway_proxy = get_zha_gateway_proxy(hass)
    try:
        ieee_address = list(registry_device.identifiers)[0][1]
        ieee = EUI64.convert(ieee_address)
    except (IndexError, ValueError) as ex:
        _LOGGER.error(
            "Unable to determine device IEEE for device with device id `%s`", device_id
        )
        raise KeyError(
            f"Unable to determine device IEEE for device with device id `{device_id}`."
        ) from ex
    return zha_gateway_proxy.device_proxies[ieee]


def cluster_command_schema_to_vol_schema(schema: CommandSchema) -> vol.Schema:
    """Convert a cluster command schema to a voluptuous schema."""
    return vol.Schema(
        {
            vol.Optional(field.name)
            if field.optional
            else vol.Required(field.name): schema_type_to_vol(field.type)
            for field in schema.fields
        }
    )


def schema_type_to_vol(field_type: Any) -> Any:
    """Convert a schema type to a voluptuous type."""
    if issubclass(field_type, enum.Flag) and field_type.__members__:
        return cv.multi_select(
            [key.replace("_", " ") for key in field_type.__members__]
        )
    if issubclass(field_type, enum.Enum) and field_type.__members__:
        return vol.In([key.replace("_", " ") for key in field_type.__members__])
    if (
        issubclass(field_type, zigpy.types.FixedIntType)
        or issubclass(field_type, enum.Flag)
        or issubclass(field_type, enum.Enum)
    ):
        return vol.All(
            vol.Coerce(int), vol.Range(field_type.min_value, field_type.max_value)
        )
    return str


def convert_to_zcl_values(
    fields: dict[str, Any], schema: CommandSchema
) -> dict[str, Any]:
    """Convert user input to ZCL values."""
    converted_fields: dict[str, Any] = {}
    for field in schema.fields:
        if field.name not in fields:
            continue
        value = fields[field.name]
        if issubclass(field.type, enum.Flag) and isinstance(value, list):
            new_value = 0

            for flag in value:
                if isinstance(flag, str):
                    new_value |= field.type[flag.replace(" ", "_")]
                else:
                    new_value |= flag

            value = field.type(new_value)
        elif issubclass(field.type, enum.Enum):
            value = (
                field.type[value.replace(" ", "_")]
                if isinstance(value, str)
                else field.type(value)
            )
        else:
            value = field.type(value)
        _LOGGER.debug(
            "Converted ZCL schema field(%s) value from: %s to: %s",
            field.name,
            fields[field.name],
            value,
        )
        converted_fields[field.name] = value
    return converted_fields


def async_cluster_exists(hass: HomeAssistant, cluster_id, skip_coordinator=True):
    """Determine if a device containing the specified in cluster is paired."""
    zha_gateway = get_zha_gateway(hass)
    zha_devices = zha_gateway.devices.values()
    for zha_device in zha_devices:
        if skip_coordinator and zha_device.is_coordinator:
            continue
        clusters_by_endpoint = zha_device.async_get_clusters()
        for clusters in clusters_by_endpoint.values():
            if (
                cluster_id in clusters[CLUSTER_TYPE_IN]
                or cluster_id in clusters[CLUSTER_TYPE_OUT]
            ):
                return True
    return False
