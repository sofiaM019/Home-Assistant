"""Constants for mobile_app."""

DOMAIN = "mobile_app"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

ATTR_FOREGROUND = "foreground"
ATTR_BACKGROUND = "background"

ATTR_DEFAULT_BEHAVIOR = "default"
ATTR_TEXT_INPUT_BEHAVIOR = "textInput"

CONF_ACTION_NAME = "name"
CONF_ACTION_BACKGROUND_COLOR = "background_color"
CONF_ACTION_LABEL = "label"
CONF_ACTION_LABEL_COLOR = "color"
CONF_ACTION_LABEL_TEXT = "text"
CONF_ACTION_ICON = "icon"
CONF_ACTION_ICON_COLOR = "color"
CONF_ACTION_ICON_ICON = "icon"
CONF_ACTIONS = "actions"

CONF_CLOUDHOOK_URL = "cloudhook_url"

CONF_ECO_IOS = "ios"

CONF_PUSH = "push"
CONF_PUSH_CATEGORIES = "categories"
CONF_PUSH_CATEGORIES_NAME = "name"
CONF_PUSH_CATEGORIES_IDENTIFIER = "identifier"
CONF_PUSH_CATEGORIES_ACTIONS = "actions"

CONF_PUSH_ACTIONS_IDENTIFIER = "identifier"
CONF_PUSH_ACTIONS_TITLE = "title"
CONF_PUSH_ACTIONS_ACTIVATION_MODE = "activationMode"
CONF_PUSH_ACTIONS_AUTHENTICATION_REQUIRED = "authenticationRequired"
CONF_PUSH_ACTIONS_DESTRUCTIVE = "destructive"
CONF_PUSH_ACTIONS_BEHAVIOR = "behavior"
CONF_PUSH_ACTIONS_CONTEXT = "context"
CONF_PUSH_ACTIONS_TEXT_INPUT_BUTTON_TITLE = "textInputButtonTitle"
CONF_PUSH_ACTIONS_TEXT_INPUT_PLACEHOLDER = "textInputPlaceholder"

CONF_REMOTE_UI_URL = "remote_ui_url"
CONF_SECRET = "secret"
CONF_USER_ID = "user_id"

DATA_BINARY_SENSOR = "binary_sensor"
DATA_CONFIG_ENTRIES = "config_entries"
DATA_DELETED_IDS = "deleted_ids"
DATA_DEVICES = "devices"
DATA_SENSOR = "sensor"
DATA_STORE = "store"

ATTR_APP_DATA = "app_data"
ATTR_APP_ID = "app_id"
ATTR_APP_NAME = "app_name"
ATTR_APP_VERSION = "app_version"
ATTR_CONFIG_ENTRY_ID = "entry_id"
ATTR_DEVICE_ID = "device_id"
ATTR_DEVICE_NAME = "device_name"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"
ATTR_OS_NAME = "os_name"
ATTR_OS_VERSION = "os_version"
ATTR_PUSH_TOKEN = "push_token"
ATTR_PUSH_URL = "push_url"
ATTR_PUSH_RATE_LIMITS = "rateLimits"
ATTR_PUSH_RATE_LIMITS_ERRORS = "errors"
ATTR_PUSH_RATE_LIMITS_MAXIMUM = "maximum"
ATTR_PUSH_RATE_LIMITS_RESETS_AT = "resetsAt"
ATTR_PUSH_RATE_LIMITS_SUCCESSFUL = "successful"
ATTR_SUPPORTS_ENCRYPTION = "supports_encryption"

ATTR_EVENT_DATA = "event_data"
ATTR_EVENT_TYPE = "event_type"

ATTR_TEMPLATE = "template"
ATTR_TEMPLATE_VARIABLES = "variables"

ATTR_SPEED = "speed"
ATTR_ALTITUDE = "altitude"
ATTR_COURSE = "course"
ATTR_VERTICAL_ACCURACY = "vertical_accuracy"

ATTR_WEBHOOK_DATA = "data"
ATTR_WEBHOOK_ENCRYPTED = "encrypted"
ATTR_WEBHOOK_ENCRYPTED_DATA = "encrypted_data"
ATTR_WEBHOOK_TYPE = "type"

ERR_ENCRYPTION_ALREADY_ENABLED = "encryption_already_enabled"
ERR_ENCRYPTION_NOT_AVAILABLE = "encryption_not_available"
ERR_ENCRYPTION_REQUIRED = "encryption_required"
ERR_SENSOR_NOT_REGISTERED = "not_registered"
ERR_INVALID_FORMAT = "invalid_format"


ATTR_SENSOR_ATTRIBUTES = "attributes"
ATTR_SENSOR_DEVICE_CLASS = "device_class"
ATTR_SENSOR_ICON = "icon"
ATTR_SENSOR_NAME = "name"
ATTR_SENSOR_STATE = "state"
ATTR_SENSOR_TYPE = "type"
ATTR_SENSOR_TYPE_BINARY_SENSOR = "binary_sensor"
ATTR_SENSOR_TYPE_SENSOR = "sensor"
ATTR_SENSOR_UNIQUE_ID = "unique_id"
ATTR_SENSOR_UOM = "unit_of_measurement"

SIGNAL_SENSOR_UPDATE = f"{DOMAIN}_sensor_update"
SIGNAL_LOCATION_UPDATE = DOMAIN + "_location_update_{}"

ATTR_CAMERA_ENTITY_ID = "camera_entity_id"
