"""Constants in Logi Circle component."""

DOMAIN = 'logi_circle'
DATA_LOGI = DOMAIN

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_API_KEY = 'api_key'
CONF_REDIRECT_URI = 'redirect_uri'

SIGNAL_LOGI_CIRCLE_UPDATE = 'logi_circle_update'


# Activity dict
ACTIVITY_PROP = 'activity'
ACTIVITY_ID = 'activity_id'
ACTIVITY_RELEVANCE = 'relevance_level'
ACTIVITY_START_TIME = 'start_time'
ACTIVITY_DURATION = 'duration'
ACTIVITY_BASE = {
    'activity_id': None,
    'relevance_level': None,
    'start_time': None,
    'duration': None
}

# Sensor types: Name, unit of measure, icon per sensor key.
LOGI_SENSORS = {
    'battery_level': [
        'Battery', '%', 'battery-50'],

    'last_activity_time': [
        'Last Activity', None, 'history'],

    'signal_strength_category': [
        'WiFi Signal Category', None, 'wifi'],

    'signal_strength_percentage': [
        'WiFi Signal Strength', '%', 'wifi'],

    'speaker_volume': [
        'Volume', '%', 'volume-high'],
}

# Binary sensor types: Name, device_class, icon
LOGI_BINARY_SENSORS = {
    'activity': [
        'Activity', 'motion', 'walk'],

    'is_charging': [
        'Charging', 'connectivity', 'battery'],

    'privacy_mode': [
        'Privacy Mode', None, 'eye'],

    'streaming_enabled': [
        'Streaming Enabled', None, 'camera']
}

# Attribution
CONF_ATTRIBUTION = "Data provided by circle.logi.com"
DEVICE_BRAND = "Logitech"
