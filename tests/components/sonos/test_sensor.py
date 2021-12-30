"""Tests for the Sonos battery sensor platform."""
from soco.exceptions import NotSupportedException

from homeassistant.components.sonos.binary_sensor import ATTR_BATTERY_POWER_SOURCE
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers import entity_registry as ent_reg


async def test_entity_registry_unsupported(hass, async_setup_sonos, soco):
    """Test sonos device without battery registered in the device registry."""
    soco.get_battery_info.side_effect = NotSupportedException

    await async_setup_sonos()

    entity_registry = ent_reg.async_get(hass)

    assert "media_player.zone_a" in entity_registry.entities
    assert "sensor.zone_a_battery" not in entity_registry.entities
    assert "binary_sensor.zone_a_power" not in entity_registry.entities


async def test_entity_registry_supported(hass, async_autosetup_sonos, soco):
    """Test sonos device with battery registered in the device registry."""
    entity_registry = ent_reg.async_get(hass)

    assert "media_player.zone_a" in entity_registry.entities
    assert "sensor.zone_a_battery" in entity_registry.entities
    assert "binary_sensor.zone_a_power" in entity_registry.entities


async def test_battery_attributes(hass, async_autosetup_sonos, soco):
    """Test sonos device with battery state."""
    entity_registry = ent_reg.async_get(hass)

    battery = entity_registry.entities["sensor.zone_a_battery"]
    battery_state = hass.states.get(battery.entity_id)
    assert battery_state.state == "100"
    assert battery_state.attributes.get("unit_of_measurement") == "%"

    power = entity_registry.entities["binary_sensor.zone_a_power"]
    power_state = hass.states.get(power.entity_id)
    assert power_state.state == STATE_ON
    assert (
        power_state.attributes.get(ATTR_BATTERY_POWER_SOURCE) == "SONOS_CHARGING_RING"
    )


async def test_battery_on_S1(hass, async_setup_sonos, soco, device_properties_event):
    """Test battery state updates on a Sonos S1 device."""
    soco.get_battery_info.return_value = {}

    await async_setup_sonos()

    subscription = soco.deviceProperties.subscribe.return_value
    sub_callback = subscription.callback

    entity_registry = ent_reg.async_get(hass)

    assert "sensor.zone_a_battery" not in entity_registry.entities
    assert "binary_sensor.zone_a_power" not in entity_registry.entities

    # Update the speaker with a callback event
    sub_callback(device_properties_event)
    await hass.async_block_till_done()

    battery = entity_registry.entities["sensor.zone_a_battery"]
    battery_state = hass.states.get(battery.entity_id)
    assert battery_state.state == "100"

    power = entity_registry.entities["binary_sensor.zone_a_power"]
    power_state = hass.states.get(power.entity_id)
    assert power_state.state == STATE_OFF
    assert power_state.attributes.get(ATTR_BATTERY_POWER_SOURCE) == "BATTERY"


async def test_device_payload_without_battery(
    hass, async_setup_sonos, soco, device_properties_event, caplog
):
    """Test device properties event update without battery info."""
    soco.get_battery_info.return_value = None

    await async_setup_sonos()

    subscription = soco.deviceProperties.subscribe.return_value
    sub_callback = subscription.callback

    bad_payload = "BadKey:BadValue"
    device_properties_event.variables["more_info"] = bad_payload

    sub_callback(device_properties_event)
    await hass.async_block_till_done()

    assert bad_payload in caplog.text


async def test_device_payload_without_battery_and_ignored_keys(
    hass, async_setup_sonos, soco, device_properties_event, caplog
):
    """Test device properties event update without battery info and ignored keys."""
    soco.get_battery_info.return_value = None

    await async_setup_sonos()

    subscription = soco.deviceProperties.subscribe.return_value
    sub_callback = subscription.callback

    ignored_payload = "SPID:InCeiling,TargetRoomName:Bouncy House"
    device_properties_event.variables["more_info"] = ignored_payload

    sub_callback(device_properties_event)
    await hass.async_block_till_done()

    assert ignored_payload not in caplog.text


async def test_audio_input_sensor(hass, async_autosetup_sonos, soco):
    """Test audio input sensor."""
    entity_registry = ent_reg.async_get(hass)

    audio_input_sensor = entity_registry.entities["sensor.zone_a_audio_input_format"]
    audio_input_state = hass.states.get(audio_input_sensor.entity_id)
    assert audio_input_state.state == "Dolby 5.1"


async def test_microphone_binary_sensor(
    hass, async_autosetup_sonos, soco, device_properties_event
):
    """Test microphone binary sensor."""
    entity_registry = ent_reg.async_get(hass)
    assert "binary_sensor.zone_a_microphone" not in entity_registry.entities

    # Update the speaker with a callback event
    subscription = soco.deviceProperties.subscribe.return_value
    subscription.callback(device_properties_event)
    await hass.async_block_till_done()

    mic_binary_sensor = entity_registry.entities["binary_sensor.zone_a_microphone"]
    mic_binary_sensor_state = hass.states.get(mic_binary_sensor.entity_id)
    assert mic_binary_sensor_state.state == STATE_ON
