"""List of tests that have uncaught exceptions today. Will be shrunk over time."""
IGNORE_UNCAUGHT_EXCEPTIONS = [
    (
        "test_homeassistant_bridge",
        "test_homeassistant_bridge_fan_setup",
    ),
    (
        "tests.components.owntracks.test_device_tracker",
        "test_mobile_multiple_async_enter_exit",
    ),
    (
        "tests.components.smartthings.test_init",
        "test_event_handler_dispatches_updated_devices",
    ),
    (
        "tests.components.unifi.test_controller",
        "test_wireless_client_event_calls_update_wireless_devices",
    ),
    ("tests.components.iaqualink.test_config_flow", "test_with_invalid_credentials"),
    ("tests.components.iaqualink.test_config_flow", "test_with_existing_config"),
    ("tests.helpers.test_event", "test_async_track_state_removed_domain"),
    ("tests.helpers.test_event", "test_async_track_state_added_domain"),
    ("tests.helpers.test_event", "test_async_track_state_change_event"),
    ("tests.helpers.test_event", "test_async_track_state_change_filtered"),
    (
        "tests.helpers.test_event",
        "test_async_track_entity_registry_updated_event_with_a_callback_that_throws",
    ),
]
