"""HTTP views to interact with the area registry."""
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.decorators import async_response
from homeassistant.core import callback
from homeassistant.helpers.area_registry import async_get_registry


DEPENDENCIES = ['websocket_api']

WS_TYPE_CREATE = 'config/area_registry/create'
SCHEMA_WS_CREATE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_CREATE,
    vol.Required('name'): str,
})

WS_TYPE_DELETE = 'config/area_registry/delete'
SCHEMA_WS_DELETE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_DELETE,
    vol.Required('id'): str,
})

WS_TYPE_LIST = 'config/area_registry/list'
SCHEMA_WS_LIST = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_LIST,
})

WS_TYPE_UPDATE = 'config/area_registry/update'
SCHEMA_WS_UPDATE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_UPDATE,
    vol.Required('id'): str,
    vol.Required('name'): str,
})


async def async_setup(hass):
    """Enable the Area Registry views."""
    hass.components.websocket_api.async_register_command(
        WS_TYPE_CREATE, websocket_create_area,
        SCHEMA_WS_CREATE
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_DELETE, websocket_delete_area,
        SCHEMA_WS_DELETE
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_LIST, websocket_list_areas,
        SCHEMA_WS_LIST
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_UPDATE, websocket_update_area,
        SCHEMA_WS_UPDATE
    )
    return True


@async_response
async def websocket_create_area(hass, connection, msg):
    """Create area command."""
    registry = await async_get_registry(hass)

    try:
        entry = registry.async_create(msg['name'])
    except ValueError as err:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'invalid_info', str(err)
        ))
    else:
        connection.send_message(websocket_api.result_message(
            msg['id'], _entry_dict(entry)
        ))


@async_response
async def websocket_delete_area(hass, connection, msg):
    """Delete area command."""
    registry = await async_get_registry(hass)

    try:
        registry.async_create(msg['area_id'])
    except ValueError as err:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'invalid_info', str(err)
        ))
    else:
        connection.send_message(websocket_api.result_message(
            msg['id'], 'success'
        ))


@async_response
async def websocket_list_areas(hass, connection, msg):
    """Handle list areas command."""
    registry = await async_get_registry(hass)
    connection.send_message(websocket_api.result_message(
        msg['id'], [{
            'name': entry.name,
            'area_id': entry.id,
        } for entry in registry.areas.values()]
    ))


@async_response
async def websocket_update_area(hass, connection, msg):
    """Handle update area websocket command."""
    registry = await async_get_registry(hass)

    try:
        entry = registry.async_update(msg['area_id'], msg['name'])
    except ValueError as err:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'invalid_info', str(err)
        ))
    else:
        connection.send_message(websocket_api.result_message(
            msg['id'], _entry_dict(entry)
        ))


@callback
def _entry_dict(entry):
    """Convert entry to API format."""
    return {
        'area_id': entry.id,
        'name': entry.name
    }
