"""Sensor for displaying the number of result from Flume."""
from numbers import Number

from pyflume import FlumeData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import VOLUME_GALLONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_SCAN_INTERVAL,
    DOMAIN,
    FLUME_AUTH,
    FLUME_DEVICES,
    FLUME_HTTP_SESSION,
    FLUME_TYPE_SENSOR,
    KEY_DEVICE_ID,
    KEY_DEVICE_LOCATION,
    KEY_DEVICE_LOCATION_NAME,
    KEY_DEVICE_LOCATION_TIMEZONE,
    KEY_DEVICE_TYPE,
)
from .coordinator import FlumeDeviceDataUpdateCoordinator
from .entity import FlumeEntity

FLUME_QUERIES_SENSOR: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="current_interval",
        name="Current",
        native_unit_of_measurement=f"{VOLUME_GALLONS}/m",
    ),
    SensorEntityDescription(
        key="month_to_date",
        name="Current Month",
        native_unit_of_measurement=VOLUME_GALLONS,
        device_class=SensorDeviceClass.VOLUME,
    ),
    SensorEntityDescription(
        key="week_to_date",
        name="Current Week",
        native_unit_of_measurement=VOLUME_GALLONS,
        device_class=SensorDeviceClass.VOLUME,
    ),
    SensorEntityDescription(
        key="today",
        name="Current Day",
        native_unit_of_measurement=VOLUME_GALLONS,
        device_class=SensorDeviceClass.VOLUME,
    ),
    SensorEntityDescription(
        key="last_60_min",
        name="60 Minutes",
        native_unit_of_measurement=f"{VOLUME_GALLONS}/h",
    ),
    SensorEntityDescription(
        key="last_24_hrs",
        name="24 Hours",
        native_unit_of_measurement=f"{VOLUME_GALLONS}/d",
    ),
    SensorEntityDescription(
        key="last_30_days",
        name="30 Days",
        native_unit_of_measurement=f"{VOLUME_GALLONS}/mo",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flume sensor."""

    flume_domain_data = hass.data[DOMAIN][config_entry.entry_id]

    flume_auth = flume_domain_data[FLUME_AUTH]
    http_session = flume_domain_data[FLUME_HTTP_SESSION]
    flume_devices = flume_domain_data[FLUME_DEVICES]

    flume_entity_list = []
    for device in flume_devices.device_list:
        if (
            device[KEY_DEVICE_TYPE] != FLUME_TYPE_SENSOR
            or KEY_DEVICE_LOCATION not in device
        ):
            continue
        if KEY_DEVICE_LOCATION not in device.keys():
            continue

        device_id = device[KEY_DEVICE_ID]
        device_timezone = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_TIMEZONE]
        device_location_name = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_NAME]

        flume_device = FlumeData(
            flume_auth,
            device_id,
            device_timezone,
            scan_interval=DEVICE_SCAN_INTERVAL,
            update_on_init=False,
            http_session=http_session,
        )

        coordinator = FlumeDeviceDataUpdateCoordinator(
            hass=hass, flume_device=flume_device
        )

        flume_entity_list.extend(
            [
                FlumeSensor(
                    coordinator=coordinator,
                    description=description,
                    device_id=device_id,
                    location_name=device_location_name,
                )
                for description in FLUME_SENSORS
            ]
        )

    if flume_entity_list:
        async_add_entities(flume_entity_list)


class FlumeSensor(FlumeEntity, SensorEntity):
    """Representation of the Flume sensor."""

    coordinator: FlumeDeviceDataUpdateCoordinator

    @property
    def native_value(self):
        """Return the state of the sensor."""
        sensor_key = self.entity_description.key
        if sensor_key not in self.coordinator.flume_device.values:
            return None

        return _format_state_value(self.coordinator.flume_device.values[sensor_key])


def _format_state_value(value):
    return round(value, 1) if isinstance(value, Number) else None
