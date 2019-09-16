"""Support for Genius Hub binary_sensor devices."""
from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.util.dt import utc_from_timestamp

from . import DOMAIN, GeniusEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Genius Hub sensor entities."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]

    switches = [
        GeniusBinarySensor(d)
        for d in client.device_objs
        if "outputOnOff" in d.data["state"]
    ]

    async_add_entities(switches)


class GeniusBinarySensor(GeniusEntity, BinarySensorDevice):
    """Representation of a Genius Hub binary_sensor."""

    def __init__(self, device) -> None:
        """Initialize the binary sensor."""
        super().__init__()

        self._device = device
        if device.type[:21] == "Dual Channel Receiver":
            self._name = f"Dual Channel Receiver {device.id}"
        else:
            self._name = f"{device.type} {device.id}"

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._device.data["state"]["outputOnOff"]

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device state attributes."""
        attrs = {}
        attrs["assigned_zone"] = self._device.data["assignedZones"][0]["name"]

        attrs["state"] = dict(self._device.data["state"])
        attrs["state"].update(self._device.data["_state"])
        attrs["state"].pop("outputOnOff")
        attrs["state"].pop("lastComms")

        last_comms = self._device.data["_state"]["lastComms"]
        if last_comms != 0:
            attrs["last_comms"] = utc_from_timestamp(last_comms).isoformat()

        return attrs
