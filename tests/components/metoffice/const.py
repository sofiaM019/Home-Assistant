"""Helpers for testing Met Office DataPoint."""

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

TEST_API_KEY = "test-metoffice-api-key"

TEST_LATITUDE_WAVERTREE = 53.38374
TEST_LONGITUDE_WAVERTREE = -2.90929
TEST_SITE_NAME_WAVERTREE = "Wavertree"

TEST_LATITUDE_KINGSLYNN = 52.75556
TEST_LONGITUDE_KINGSLYNN = 0.44231
TEST_SITE_NAME_KINGSLYNN = "King's Lynn"

METOFFICE_CONFIG_WAVERTREE = {
    CONF_API_KEY: TEST_API_KEY,
    CONF_LATITUDE: TEST_LATITUDE_WAVERTREE,
    CONF_LONGITUDE: TEST_LONGITUDE_WAVERTREE,
    CONF_NAME: TEST_SITE_NAME_WAVERTREE,
}

METOFFICE_CONFIG_KINGSLYNN = {
    CONF_API_KEY: TEST_API_KEY,
    CONF_LATITUDE: TEST_LATITUDE_KINGSLYNN,
    CONF_LONGITUDE: TEST_LONGITUDE_KINGSLYNN,
    CONF_NAME: TEST_SITE_NAME_KINGSLYNN,
}

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S%z"
