"""Device discovery functions for Zigbee Home Automation."""

from collections import Counter
import logging
from typing import Callable, List, Tuple

from homeassistant import const as ha_const
from homeassistant.core import callback
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers.typing import HomeAssistantType

from . import const as zha_const, registries as zha_regs, typing as zha_typing
from .. import (  # noqa: F401 pylint: disable=unused-import,
    binary_sensor,
    cover,
    device_tracker,
    fan,
    light,
    lock,
    sensor,
    switch,
)
from .channels import base

_LOGGER = logging.getLogger(__name__)


@callback
async def async_add_entities(
    _async_add_entities: Callable,
    entities: List[
        Tuple[
            zha_typing.ZhaEntityType,
            Tuple[str, zha_typing.ZhaDeviceType, List[zha_typing.ChannelType]],
        ]
    ],
) -> None:
    """Add entities helper."""
    if not entities:
        return
    to_add = [ent_cls(*args) for ent_cls, args in entities]
    _async_add_entities(to_add, update_before_add=True)
    entities.clear()


class ProbeEndpoint:
    """All discovered channels and entities of an endpoint."""

    def __init__(self):
        """Initialize instance."""
        self._device_configs = {}

    @callback
    def discover_entities(self, channel_pool: zha_typing.ChannelPoolType) -> None:
        """Process an endpoint on a zigpy device."""
        self.discover_by_device_type(channel_pool)
        self.discover_by_cluster_id(channel_pool)

    @callback
    def discover_by_device_type(self, channel_pool: zha_typing.ChannelPoolType) -> None:
        """Process an endpoint on a zigpy device."""

        unique_id = channel_pool.unique_id

        component = self._device_configs.get(unique_id, {}).get(ha_const.CONF_TYPE)
        if component is None:
            ep_profile_id = channel_pool.endpoint.profile_id
            ep_device_type = channel_pool.endpoint.device_type
            component = zha_regs.DEVICE_CLASS[ep_profile_id].get(ep_device_type)

        if component and component in zha_const.COMPONENTS:
            channels = channel_pool.unclaimed_channels()
            entity_class, claimed = zha_regs.ZHA_ENTITIES.get_entity(
                component, channel_pool.manufacturer, channel_pool.model, channels
            )
            if entity_class is None:
                return
            channel_pool.claim_channels(claimed)
            channel_pool.async_new_entity(component, entity_class, unique_id, claimed)

    @callback
    def discover_by_cluster_id(self, channel_pool: zha_typing.ChannelPoolType) -> None:
        """Process an endpoint on a zigpy device."""

        items = zha_regs.SINGLE_INPUT_CLUSTER_DEVICE_CLASS.items()
        single_input_clusters = {
            cluster_class: match
            for cluster_class, match in items
            if not isinstance(cluster_class, int)
        }
        remaining_channels = channel_pool.unclaimed_channels()
        for channel in remaining_channels:
            if channel.cluster.cluster_id in zha_regs.CHANNEL_ONLY_CLUSTERS:
                channel_pool.claim_channels([channel])
                continue

            component = zha_regs.SINGLE_INPUT_CLUSTER_DEVICE_CLASS.get(
                channel.cluster.cluster_id
            )
            if component is None:
                for cluster_class, match in single_input_clusters.items():
                    if isinstance(channel.cluster, cluster_class):
                        component = match
                        break

            self.probe_single_cluster(component, channel, channel_pool)

        # until we can get rid off registries
        self.handle_on_off_output_cluster_exception(channel_pool)

    @staticmethod
    def probe_single_cluster(
        component: str,
        channel: zha_typing.ChannelType,
        ep_channels: zha_typing.ChannelPoolType,
    ) -> None:
        """Probe specified cluster for specific component."""
        if component is None or component not in zha_const.COMPONENTS:
            return
        channel_list = [channel]
        unique_id = f"{ep_channels.unique_id}-{channel.cluster.cluster_id}"

        entity_class, claimed = zha_regs.ZHA_ENTITIES.get_entity(
            component, ep_channels.manufacturer, ep_channels.model, channel_list
        )
        if entity_class is None:
            return
        ep_channels.claim_channels(claimed)
        ep_channels.async_new_entity(component, entity_class, unique_id, claimed)

    def handle_on_off_output_cluster_exception(
        self, ep_channels: zha_typing.ChannelPoolType
    ) -> None:
        """Process output clusters of the endpoint."""

        profile_id = ep_channels.endpoint.profile_id
        device_type = ep_channels.endpoint.device_type
        if device_type in zha_regs.REMOTE_DEVICE_TYPES.get(profile_id, []):
            return

        for cluster_id, cluster in ep_channels.endpoint.out_clusters.items():
            component = zha_regs.SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS.get(
                cluster.cluster_id
            )
            if component is None:
                continue

            channel_class = zha_regs.ZIGBEE_CHANNEL_REGISTRY.get(
                cluster_id, base.ZigbeeChannel
            )
            channel = channel_class(cluster, ep_channels)
            self.probe_single_cluster(component, channel, ep_channels)

    def initialize(self, hass: HomeAssistantType) -> None:
        """Update device overrides config."""
        zha_config = hass.data[zha_const.DATA_ZHA].get(zha_const.DATA_ZHA_CONFIG, {})
        overrides = zha_config.get(zha_const.CONF_DEVICE_CONFIG)
        if overrides:
            self._device_configs.update(overrides)


class GroupProbe:
    """Determine the appropriate component for a group."""

    def __init__(self):
        """Initialize instance."""
        self._hass = None

    def initialize(self, hass: HomeAssistantType) -> None:
        """Initialize the group probe."""
        self._hass = hass

    @callback
    def discover_group_entities(self, group: zha_typing.ZhaGroupType) -> None:
        """Process a group and create any entities that are needed."""
        # only create a group entity if there are 2 or more members in a group
        if len(group.members) < 2:
            return

        if group.entity_domain is None:
            group.entity_domain = GroupProbe.determine_default_entity_domain(
                self._hass, group
            )
        if group.entity_domain is not None:
            zha_gateway = self._hass.data[zha_const.DATA_ZHA][
                zha_const.DATA_ZHA_GATEWAY
            ]
            entity_class = zha_regs.ZHA_ENTITIES.get_group_entity(group.entity_domain)
            if entity_class is not None:
                self._hass.data[zha_const.DATA_ZHA][group.entity_domain].append(
                    (
                        entity_class,
                        (
                            group.domain_entity_ids,
                            f"light_group_{group.group_id}",
                            group.group_id,
                            zha_gateway.coordinator_zha_device,
                        ),
                    )
                )

    @staticmethod
    def determine_default_entity_domain(
        hass: HomeAssistantType, group: zha_typing.ZhaGroupType
    ):
        """Determine the default entity domain for this group."""
        if len(group.members) < 2:
            _LOGGER.debug(
                "Group: %s:0x%04x has less than 2 members so cannot default an entity domain",
                group.name,
                group.group_id,
            )
            return None

        zha_gateway = hass.data[zha_const.DATA_ZHA][zha_const.DATA_ZHA_GATEWAY]
        all_domain_occurrences = []
        for device in group.members:
            entities = async_entries_for_device(
                zha_gateway.ha_entity_registry, device.device_id
            )
            all_domain_occurrences.extend(
                [
                    entity.domain
                    for entity in entities
                    if entity.domain in zha_regs.GROUP_ENTITY_DOMAINS
                ]
            )
        counts = Counter(all_domain_occurrences)
        domain = counts.most_common(1)[0][0]
        _LOGGER.debug(
            "The default entity domain is: %s for group: %s:0x%04x",
            domain,
            group.name,
            group.group_id,
        )
        return domain


PROBE = ProbeEndpoint()
GROUP_PROBE = GroupProbe()
