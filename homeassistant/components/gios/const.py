"""Constants for GIOS integration."""
ATTR_NAME = "name"
ATTR_STATION = "station"
CONF_STATION_ID = "station_id"
DATA_CLIENT = "client"
DEFAULT_NAME = "GIOŚ"
DOMAIN = "gios"

AQI_GOOD = "dobry"
AQI_MODERATE = "umiarkowany"
AQI_POOR = "dostateczny"
AQI_VERY_GOOD = "bardzo dobry"
AQI_VERY_POOR = "zły"

ICONS_MAP = {
    AQI_VERY_GOOD: "mdi:emoticon-excited",
    AQI_GOOD: "mdi:emoticon-happy",
    AQI_MODERATE: "mdi:emoticon-neutral",
    AQI_POOR: "mdi:emoticon-sad",
    AQI_VERY_POOR: "mdi:emoticon-dead",
}
