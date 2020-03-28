"""List of modules that have uncaught exceptions today. Will be shrunk over time."""
IGNORE_UNCAUGHT_EXCEPTIONS = [
    ("tests.components.cast.test_media_player", "test_start_discovery_called_once"),
    ("tests.components.cast.test_media_player", "test_entry_setup_single_config"),
    ("tests.components.cast.test_media_player", "test_entry_setup_list_config"),
    ("tests.components.cast.test_media_player", "test_entry_setup_platform_not_ready"),
    ("tests.components.config.test_automation", "test_delete_automation"),
    ("tests.components.config.test_group", "test_update_device_config"),
    ("tests.components.deconz.test_binary_sensor", "test_allow_clip_sensor"),
    ("tests.components.deconz.test_climate", "test_clip_climate_device"),
    ("tests.components.deconz.test_init", "test_unload_entry_multiple_gateways"),
    ("tests.components.deconz.test_light", "test_disable_light_groups"),
    ("tests.components.deconz.test_sensor", "test_allow_clip_sensors"),
    ("tests.components.default_config.test_init", "test_setup"),
    ("tests.components.demo.test_init", "test_setting_up_demo"),
    ("tests.components.discovery.test_init", "test_discover_config_flow"),
    ("tests.components.dsmr.test_sensor", "test_default_setup"),
    ("tests.components.dsmr.test_sensor", "test_v4_meter"),
    ("tests.components.dsmr.test_sensor", "test_v5_meter"),
    ("tests.components.dsmr.test_sensor", "test_belgian_meter"),
    ("tests.components.dsmr.test_sensor", "test_belgian_meter_low"),
    ("tests.components.dsmr.test_sensor", "test_tcp"),
    ("tests.components.dsmr.test_sensor", "test_connection_errors_retry"),
    ("tests.components.dynalite.test_bridge", "test_add_devices_then_register"),
    ("tests.components.dynalite.test_bridge", "test_register_then_add_devices"),
    ("tests.components.dynalite.test_config_flow", "test_existing_update"),
    ("tests.components.dyson.test_air_quality", "test_purecool_aiq_attributes"),
    ("tests.components.dyson.test_air_quality", "test_purecool_aiq_update_state"),
    (
        "tests.components.dyson.test_air_quality",
        "test_purecool_component_setup_only_once",
    ),
    ("tests.components.dyson.test_air_quality", "test_purecool_aiq_without_discovery"),
    (
        "tests.components.dyson.test_air_quality",
        "test_purecool_aiq_empty_environment_state",
    ),
    (
        "tests.components.dyson.test_climate",
        "test_setup_component_with_parent_discovery",
    ),
    ("tests.components.dyson.test_fan", "test_purecoollink_attributes"),
    ("tests.components.dyson.test_fan", "test_purecool_turn_on"),
    ("tests.components.dyson.test_fan", "test_purecool_set_speed"),
    ("tests.components.dyson.test_fan", "test_purecool_turn_off"),
    ("tests.components.dyson.test_fan", "test_purecool_set_dyson_speed"),
    ("tests.components.dyson.test_fan", "test_purecool_oscillate"),
    ("tests.components.dyson.test_fan", "test_purecool_set_night_mode"),
    ("tests.components.dyson.test_fan", "test_purecool_set_auto_mode"),
    ("tests.components.dyson.test_fan", "test_purecool_set_angle"),
    ("tests.components.dyson.test_fan", "test_purecool_set_flow_direction_front"),
    ("tests.components.dyson.test_fan", "test_purecool_set_timer"),
    ("tests.components.dyson.test_fan", "test_purecool_update_state"),
    ("tests.components.dyson.test_fan", "test_purecool_update_state_filter_inv"),
    ("tests.components.dyson.test_fan", "test_purecool_component_setup_only_once"),
    ("tests.components.dyson.test_sensor", "test_purecool_component_setup_only_once"),
    ("tests.components.gdacs.test_geo_location", "test_setup"),
    ("tests.components.gdacs.test_sensor", "test_setup"),
    ("tests.components.geonetnz_quakes.test_geo_location", "test_setup"),
    ("tests.components.geonetnz_quakes.test_sensor", "test_setup"),
    ("test_homeassistant_bridge", "test_homeassistant_bridge_fan_setup"),
    ("tests.components.homematicip_cloud.test_config_flow", "test_flow_works"),
    ("tests.components.homematicip_cloud.test_config_flow", "test_import_config"),
    ("tests.components.homematicip_cloud.test_device", "test_hmip_remove_group"),
    (
        "tests.components.homematicip_cloud.test_init",
        "test_config_with_accesspoint_passed_to_config_entry",
    ),
    (
        "tests.components.homematicip_cloud.test_init",
        "test_config_already_registered_not_passed_to_config_entry",
    ),
    (
        "tests.components.homematicip_cloud.test_init",
        "test_load_entry_fails_due_to_generic_exception",
    ),
    ("tests.components.hue.test_bridge", "test_handle_unauthorized"),
    ("tests.components.hue.test_init", "test_security_vuln_check"),
    ("tests.components.hue.test_light", "test_group_features"),
    ("tests.components.ios.test_init", "test_creating_entry_sets_up_sensor"),
    ("tests.components.ios.test_init", "test_not_configuring_ios_not_creates_entry"),
    ("tests.components.local_file.test_camera", "test_file_not_readable"),
    ("tests.components.meteo_france.test_config_flow", "test_user"),
    ("tests.components.meteo_france.test_config_flow", "test_import"),
    ("tests.components.mikrotik.test_device_tracker", "test_restoring_devices"),
    ("tests.components.mikrotik.test_hub", "test_arp_ping"),
    ("tests.components.mqtt.test_alarm_control_panel", "test_unique_id"),
    ("tests.components.mqtt.test_binary_sensor", "test_unique_id"),
    ("tests.components.mqtt.test_camera", "test_unique_id"),
    ("tests.components.mqtt.test_climate", "test_unique_id"),
    ("tests.components.mqtt.test_cover", "test_unique_id"),
    ("tests.components.mqtt.test_fan", "test_unique_id"),
    (
        "tests.components.mqtt.test_init",
        "test_setup_uses_certificate_on_certificate_set_to_auto",
    ),
    (
        "tests.components.mqtt.test_init",
        "test_setup_does_not_use_certificate_on_mqtts_port",
    ),
    (
        "tests.components.mqtt.test_init",
        "test_setup_without_tls_config_uses_tlsv1_under_python36",
    ),
    (
        "tests.components.mqtt.test_init",
        "test_setup_with_tls_config_uses_tls_version1_2",
    ),
    (
        "tests.components.mqtt.test_init",
        "test_setup_with_tls_config_of_v1_under_python36_only_uses_v1",
    ),
    ("tests.components.mqtt.test_legacy_vacuum", "test_unique_id"),
    ("tests.components.mqtt.test_light", "test_unique_id"),
    ("tests.components.mqtt.test_light", "test_entity_device_info_remove"),
    ("tests.components.mqtt.test_light_json", "test_unique_id"),
    ("tests.components.mqtt.test_light_json", "test_entity_device_info_remove"),
    ("tests.components.mqtt.test_light_template", "test_entity_device_info_remove"),
    ("tests.components.mqtt.test_lock", "test_unique_id"),
    ("tests.components.mqtt.test_sensor", "test_unique_id"),
    ("tests.components.mqtt.test_state_vacuum", "test_unique_id"),
    ("tests.components.mqtt.test_switch", "test_unique_id"),
    ("tests.components.mqtt.test_switch", "test_entity_device_info_remove"),
    ("tests.components.plex.test_config_flow", "test_import_success"),
    ("tests.components.plex.test_config_flow", "test_single_available_server"),
    ("tests.components.plex.test_config_flow", "test_multiple_servers_with_selection"),
    ("tests.components.plex.test_config_flow", "test_adding_last_unconfigured_server"),
    ("tests.components.plex.test_config_flow", "test_option_flow"),
    ("tests.components.plex.test_config_flow", "test_option_flow_new_users_available"),
    ("tests.components.plex.test_init", "test_setup_with_config"),
    ("tests.components.plex.test_init", "test_setup_with_config_entry"),
    ("tests.components.plex.test_init", "test_set_config_entry_unique_id"),
    ("tests.components.plex.test_init", "test_setup_with_insecure_config_entry"),
    ("tests.components.plex.test_init", "test_setup_with_photo_session"),
    ("tests.components.plex.test_server", "test_new_users_available"),
    ("tests.components.plex.test_server", "test_new_ignored_users_available"),
    ("tests.components.plex.test_server", "test_mark_sessions_idle"),
    ("tests.components.qwikswitch.test_init", "test_binary_sensor_device"),
    ("tests.components.qwikswitch.test_init", "test_sensor_device"),
    ("tests.components.rflink.test_init", "test_send_command_invalid_arguments"),
    ("tests.components.samsungtv.test_media_player", "test_update_connection_failure"),
    ("tests.components.tplink.test_init", "test_configuring_device_types"),
    (
        "tests.components.tplink.test_init",
        "test_configuring_devices_from_multiple_sources",
    ),
    ("tests.components.tradfri.test_light", "test_light"),
    ("tests.components.tradfri.test_light", "test_light_observed"),
    ("tests.components.tradfri.test_light", "test_light_available"),
    ("tests.components.tradfri.test_light", "test_turn_on"),
    ("tests.components.tradfri.test_light", "test_turn_off"),
    ("tests.components.unifi_direct.test_device_tracker", "test_get_scanner"),
    ("tests.components.upnp.test_init", "test_async_setup_entry_default"),
    ("tests.components.upnp.test_init", "test_async_setup_entry_port_mapping"),
    ("tests.components.vera.test_init", "test_init"),
    ("tests.components.wunderground.test_sensor", "test_fails_because_of_unique_id"),
    ("tests.components.yr.test_sensor", "test_default_setup"),
    ("tests.components.yr.test_sensor", "test_custom_setup"),
    ("tests.components.yr.test_sensor", "test_forecast_setup"),
    ("tests.components.zwave.test_init", "test_power_schemes"),
    (
        "tests.helpers.test_entity_platform",
        "test_adding_entities_with_generator_and_thread_callback",
    ),
    (
        "tests.helpers.test_entity_platform",
        "test_not_adding_duplicate_entities_with_unique_id",
    ),
]
