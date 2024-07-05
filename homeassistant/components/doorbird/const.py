"""The DoorBird integration constants."""

from homeassistant.const import Platform

DOMAIN = "doorbird"
PLATFORMS = [Platform.BUTTON, Platform.CAMERA, Platform.EVENT]
DOOR_STATION = "door_station"
DOOR_STATION_INFO = "door_station_info"
DOOR_STATION_EVENT_ENTITY_IDS = "door_station_event_entity_ids"

CONF_EVENTS = "events"
MANUFACTURER = "Bird Home Automation Group"
DOORBIRD_OUI = "1CCAE3"

DOORBIRD_INFO_KEY_FIRMWARE = "FIRMWARE"
DOORBIRD_INFO_KEY_BUILD_NUMBER = "BUILD_NUMBER"
DOORBIRD_INFO_KEY_DEVICE_TYPE = "DEVICE-TYPE"
DOORBIRD_INFO_KEY_RELAYS = "RELAYS"
DOORBIRD_INFO_KEY_PRIMARY_MAC_ADDR = "PRIMARY_MAC_ADDR"
DOORBIRD_INFO_KEY_WIFI_MAC_ADDR = "WIFI_MAC_ADDR"

UNDO_UPDATE_LISTENER = "undo_update_listener"

API_URL = f"/api/{DOMAIN}"
