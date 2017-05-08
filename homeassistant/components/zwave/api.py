"""API class to give info to the Z-Wave panel."""

import logging
import homeassistant.core as ha
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import HTTP_NOT_FOUND
from . import const

_LOGGER = logging.getLogger(__name__)

ZWAVE_NETWORK = 'zwave_network'


class ZWaveNodeGroupView(HomeAssistantView):
    """View to return the nodes group configuration."""

    url = r"/api/zwave/groups/{node_id:\d+}"
    name = "api:zwave:groups"

    @ha.callback
    def get(self, request, node_id):
        """Retrieve groups of node."""
        # pylint: disable=import-error
        from openzwave.group import ZWaveGroup

        nodeid = int(node_id)
        hass = request.app['hass']
        network = hass.data.get(ZWAVE_NETWORK)
        node = network.nodes.get(nodeid)
        if node is None:
            return self.json_message('Node not found', HTTP_NOT_FOUND)
        groupdata = node.groups_to_dict()
        groups = {}
        for key in groupdata:
            groupnode = ZWaveGroup(key, network, nodeid)
            groups[key] = {'associations': groupnode.associations,
                           'association_instances':
                           groupnode.associations_instances,
                           'label': groupnode.label,
                           'max_associations': groupnode.max_associations}
        return self.json(groups)


class ZWaveNodeConfigView(HomeAssistantView):
    """View to return the nodes configuration options."""

    url = r"/api/zwave/config/{node_id:\d+}"
    name = "api:zwave:config"

    @ha.callback
    def get(self, request, node_id):
        """Retrieve configurations of node."""
        nodeid = int(node_id)
        hass = request.app['hass']
        network = hass.data.get(ZWAVE_NETWORK)
        node = network.nodes.get(nodeid)
        if node is None:
            return self.json_message('Node not found', HTTP_NOT_FOUND)
        config = {}
        for value in (
                node.get_values(class_id=const.COMMAND_CLASS_CONFIGURATION)
                .values()):
            config[value.index] = {'label': value.label,
                                   'type': value.type,
                                   'help': value.help,
                                   'data_items': value.data_items,
                                   'data': value.data,
                                   'max': value.max,
                                   'min': value.min}
        return self.json(config)


class ZWaveUserCodeView(HomeAssistantView):
    """View to return the nodes usercode configuration."""

    url = r"/api/zwave/usercodes/{node_id:\d+}"
    name = "api:zwave:usercodes"

    @ha.callback
    def get(self, request, node_id):
        """Retrieve usercodes of node."""
        nodeid = int(node_id)
        hass = request.app['hass']
        network = hass.data.get(ZWAVE_NETWORK)
        node = network.nodes.get(nodeid)
        if node is None:
            return self.json_message('Node not found', HTTP_NOT_FOUND)
        usercodes = {}
        if not node.has_command_class(const.COMMAND_CLASS_USER_CODE):
            return self.json(usercodes, HTTP_NOT_FOUND)
        for value in (
                node.get_values(class_id=const.COMMAND_CLASS_USER_CODE)
                .values()):
            if value.genre != const.GENRE_USER:
                continue
            usercodes[value.index] = {'code': value.data,
                                      'label': value.label,
                                      'length': len(value.data)}
        return self.json(usercodes)
