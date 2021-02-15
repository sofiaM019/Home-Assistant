"""Represent the AsusWrt router."""
from datetime import datetime, timedelta
import enum
import logging
from typing import Any, Dict, Optional

from aioasuswrt.asuswrt import AsusWrt

from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    DOMAIN as TRACKER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    CONF_TRACK_UNKNOWN,
    DEFAULT_DNSMASQ,
    DEFAULT_INTERFACE,
    DEFAULT_TRACK_UNKNOWN,
    DOMAIN,
    PROTOCOL_TELNET,
    SENSOR_CONNECTED_DEVICE,
    SENSOR_RX_BYTES,
    SENSOR_RX_RATES,
    SENSOR_TX_BYTES,
    SENSOR_TX_RATES,
)

CONF_REQ_RELOAD = [CONF_DNSMASQ, CONF_INTERFACE, CONF_REQUIRE_IP]
SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


class AsusWrtSensorType(enum.IntEnum):
    """Enun possible AsusWrt sensor types."""

    TypeNone = 0
    TypeCount = 1
    TypeBytes = 2
    TypeRates = 3


class AsusWrtSensorData:
    """Representation of AsusWrt sensor data."""

    def __init__(self, sensor_type: AsusWrtSensorType, value=None):
        """Initialize a AsusWrt sensor data."""
        self.type = sensor_type
        self.value = value
        self._enabled = False

    def enable(self):
        """Set sensor enabled."""
        self._enabled = True

    def disable(self):
        """Set sensor disabled."""
        self._enabled = False

    @property
    def enabled(self):
        """Return sensor state."""
        return self._enabled


class AsusWrtDevInfo:
    """Representation of a AsusWrt device info."""

    def __init__(self, mac, name=None):
        """Initialize a AsusWrt device info."""
        self._mac = mac
        self._name = name
        self._ip_address = None
        self._last_activity = None
        self._connected = False

    def update(self, dev_info=None, consider_home=0):
        """Update AsusWrt device info."""
        utc_point_in_time = dt_util.utcnow()
        if dev_info:
            if not self._name:
                self._name = dev_info.name or self._mac.replace(":", "_")
            self._ip_address = dev_info.ip
            self._last_activity = utc_point_in_time
            self._connected = True

        elif self._connected:
            self._connected = (
                utc_point_in_time - self._last_activity
            ).total_seconds() < consider_home
            self._ip_address = None

    @property
    def is_connected(self):
        """Return connected status."""
        return self._connected

    @property
    def mac(self):
        """Return device mac address."""
        return self._mac

    @property
    def name(self):
        """Return device name."""
        return self._name

    @property
    def ip_address(self):
        """Return device ip address."""
        return self._ip_address

    @property
    def last_activity(self):
        """Return device last activity."""
        return self._last_activity


class AsusWrtRouter:
    """Representation of a AsusWrt router."""

    def __init__(self, hass: HomeAssistantType, entry: ConfigEntry) -> None:
        """Initialize a AsusWrt router."""
        self.hass = hass
        self._entry = entry

        self._api: AsusWrt = None
        self._protocol = entry.data[CONF_PROTOCOL]
        self._host = entry.data[CONF_HOST]

        self._devices: Dict[str, Any] = {}
        self._connect_error = False

        self._connected_devices = 0
        self._sensors: Dict[str, AsusWrtSensorData] = {}
        self._api_error: Dict[str, bool] = {}

        self._on_close = []

        self._options = {
            CONF_DNSMASQ: DEFAULT_DNSMASQ,
            CONF_INTERFACE: DEFAULT_INTERFACE,
            CONF_REQUIRE_IP: True,
        }
        self._options.update(entry.options)

    async def setup(self) -> None:
        """Set up a AsusWrt router."""
        self._api = get_api(self._entry.data, self._options)

        try:
            await self._api.connection.async_connect()
        except OSError as exp:
            raise ConfigEntryNotReady from exp

        if not self._api.is_connected:
            raise ConfigEntryNotReady

        # Load tracked entities from registry
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        track_entries = (
            self.hass.helpers.entity_registry.async_entries_for_config_entry(
                entity_registry, self._entry.entry_id
            )
        )
        for entry in track_entries:
            if entry.domain == TRACKER_DOMAIN:
                self._devices[entry.unique_id] = AsusWrtDevInfo(
                    entry.unique_id, entry.original_name
                )

        # Init Sensors
        self._sensors = {
            SENSOR_CONNECTED_DEVICE: AsusWrtSensorData(AsusWrtSensorType.TypeCount),
            SENSOR_RX_BYTES: AsusWrtSensorData(AsusWrtSensorType.TypeBytes),
            SENSOR_TX_BYTES: AsusWrtSensorData(AsusWrtSensorType.TypeBytes),
            SENSOR_RX_RATES: AsusWrtSensorData(AsusWrtSensorType.TypeRates),
            SENSOR_TX_RATES: AsusWrtSensorData(AsusWrtSensorType.TypeRates),
        }

        # Update all
        await self.update_all()

        self.async_on_close(
            async_track_time_interval(self.hass, self.update_all, SCAN_INTERVAL)
        )

    async def update_all(self, now: Optional[datetime] = None) -> None:
        """Update all AsusWrt platforms."""
        await self.update_devices()
        await self.update_sensors()

    async def update_devices(self) -> None:
        """Update AsusWrt devices tracker."""
        new_device = False
        _LOGGER.debug("Checking devices for ASUS router %s", self._host)
        try:
            wrt_devices = await self._api.async_get_connected_devices()
        except OSError as exc:
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.error(
                    "Error connecting to ASUS router %s for device update: %s",
                    self._host,
                    exc,
                )
            return

        if self._connect_error:
            self._connect_error = False
            _LOGGER.info("Reconnected to ASUS router %s", self._host)

        self._connected_devices = len(wrt_devices)
        consider_home = self._options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )
        track_unknown = self._options.get(CONF_TRACK_UNKNOWN, DEFAULT_TRACK_UNKNOWN)

        for device_mac in self._devices:
            dev_info = wrt_devices.get(device_mac)
            self._devices[device_mac].update(dev_info, consider_home)

        for device_mac, dev_info in wrt_devices.items():
            if device_mac in self._devices:
                continue
            if not track_unknown and not dev_info.name:
                continue
            new_device = True
            device = AsusWrtDevInfo(device_mac)
            device.update(dev_info)
            self._devices[device_mac] = device

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    async def update_sensors(self) -> None:
        """Update AsusWrt sensors."""
        self._sensors[SENSOR_CONNECTED_DEVICE].value = self._connected_devices

        if self.has_sensor_type(AsusWrtSensorType.TypeBytes):
            try:
                datas = await self._api.async_get_bytes_total()
            except OSError:
                self._log_api_method("async_get_bytes_total", True)
            else:
                self._log_api_method("async_get_bytes_total", False)
                self._sensors[SENSOR_RX_BYTES].value = datas[0]
                self._sensors[SENSOR_TX_BYTES].value = datas[1]

        if self.has_sensor_type(AsusWrtSensorType.TypeRates):
            try:
                rates = await self._api.async_get_current_transfer_rates()
            except OSError:
                self._log_api_method("async_get_current_transfer_rates", True)
            else:
                self._log_api_method("async_get_current_transfer_rates", False)
                self._sensors[SENSOR_RX_RATES].value = rates[0]
                self._sensors[SENSOR_TX_RATES].value = rates[1]

        async_dispatcher_send(self.hass, self.signal_sensor_update)

    def has_sensor_type(self, sensor_type: AsusWrtSensorType):
        """Return if an AsusWrt sensor type is enabled."""
        for sensor in (x for x in self._sensors.values() if x.type == sensor_type):
            if sensor.enabled:
                return True
        return False

    def _log_api_method(self, method, error):
        """Log call result to AsusWrt api method."""
        prev_error = self._api_error.get(method, False)
        if not error or prev_error:
            return

        if error:
            _LOGGER.error("Error executing method %s", method)
            self._api_error[method] = True
        elif prev_error:
            _LOGGER.info("Method %s successfully executed", method)
            self._api_error[method] = False

    async def close(self) -> None:
        """Close the connection."""
        if self._api is not None:
            if self._protocol == PROTOCOL_TELNET:
                await self._api.connection.disconnect()
        self._api = None

        for func in self._on_close:
            func()
        self._on_close.clear()

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    def update_options(self, new_options: Dict) -> bool:
        """Update router options."""
        req_reload = False
        for name, new_opt in new_options.items():
            if name in (CONF_REQ_RELOAD):
                old_opt = self._options.get(name)
                if not old_opt or old_opt != new_opt:
                    req_reload = True
                    break

        self._options.update(new_options)
        return req_reload

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, "AsusWRT")},
            "name": self._host,
            "model": "Asus Router",
            "manufacturer": "Asus",
        }

    @property
    def signal_device_new(self) -> str:
        """Event specific per AsusWrt entry to signal new device."""
        return f"{DOMAIN}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per AsusWrt entry to signal updates in devices."""
        return f"{DOMAIN}-device-update"

    @property
    def signal_sensor_update(self) -> str:
        """Event specific per AsusWrt entry to signal updates in sensors."""
        return f"{DOMAIN}-sensor-update"

    @property
    def host(self) -> str:
        """Return router hostname."""
        return self._host

    @property
    def devices(self) -> Dict[str, Any]:
        """Return devices."""
        return self._devices

    @property
    def sensors(self) -> Dict[str, AsusWrtSensorData]:
        """Return sensors."""
        return self._sensors

    @property
    def api(self) -> AsusWrt:
        """Return router API."""
        return self._api


def get_api(conf: Dict, options: Optional[Dict] = None) -> AsusWrt:
    """Get the AsusWrt API."""
    opt = options or {}

    return AsusWrt(
        conf[CONF_HOST],
        conf[CONF_PORT],
        conf[CONF_PROTOCOL] == PROTOCOL_TELNET,
        conf[CONF_USERNAME],
        conf.get(CONF_PASSWORD, ""),
        conf.get(CONF_SSH_KEY, ""),
        conf[CONF_MODE],
        opt.get(CONF_REQUIRE_IP, True),
        interface=opt.get(CONF_INTERFACE, DEFAULT_INTERFACE),
        dnsmasq=opt.get(CONF_DNSMASQ, DEFAULT_DNSMASQ),
    )
