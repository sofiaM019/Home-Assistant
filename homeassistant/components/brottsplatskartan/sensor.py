"""Sensor platform for Brottsplatskartan information."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from brottsplatskartan import ATTRIBUTION, BrottsplatsKartan
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import AREAS, CONF_APP_ID, CONF_AREA, DEFAULT_NAME, DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(minutes=30)
ICON = "mdi:account-alert"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_AREA, default="N/A"): vol.All(cv.string, vol.In(AREAS)),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Brottsplatskartan platform."""

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2022.12.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Brottsplatskartan sensor entry."""

    area = entry.data[CONF_AREA] if entry.data[CONF_AREA] != "N/A" else None
    latitude = entry.data.get(CONF_LATITUDE, hass.config.latitude)
    longitude = entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    app = entry.data[CONF_APP_ID]
    name = entry.title
    unique_id = f"bpk-{latitude}-{longitude}-{area}"

    bpk = BrottsplatsKartan(app=app, area=area, latitude=latitude, longitude=longitude)

    async_add_entities([BrottsplatskartanSensor(bpk, name, unique_id)], True)


class BrottsplatskartanSensor(SensorEntity):
    """Representation of a Brottsplatskartan Sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = ICON
    _attr_has_entity_name = True

    def __init__(self, bpk: BrottsplatsKartan, name: str, unique_id: str) -> None:
        """Initialize the Brottsplatskartan sensor."""
        self._bpk = bpk
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Brottsplatskartan",
            name=name,
        )

    def update(self) -> None:
        """Update device state."""

        incident_counts: dict[str, int] = defaultdict(int)
        incidents = self._bpk.get_incidents()

        if incidents is False:
            LOGGER.error("Could not fetch incidents")
            return

        for incident in incidents:
            if (incident_type := incident.get("title_type")) is not None:
                incident_counts[incident_type] += 1

        self._attr_extra_state_attributes = incident_counts
        self._attr_native_value = len(incidents)
