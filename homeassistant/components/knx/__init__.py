"""Support KNX devices."""
from __future__ import annotations

import asyncio
import logging
from typing import Final

import voluptuous as vol
from xknx import XKNX
from xknx.core import XknxConnectionState
from xknx.core.telegram_queue import TelegramQueue
from xknx.dpt import DPTArray, DPTBase, DPTBinary
from xknx.exceptions import ConversionError, XKNXException
from xknx.io import ConnectionConfig, ConnectionType
from xknx.telegram import AddressFilter, Telegram
from xknx.telegram.address import (
    DeviceGroupAddress,
    GroupAddress,
    InternalGroupAddress,
    parse_device_group_address,
)
from xknx.telegram.apci import GroupValueRead, GroupValueResponse, GroupValueWrite

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_EVENT,
    CONF_HOST,
    CONF_PORT,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_EXPOSE,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_ROUTING,
    CONF_KNX_TUNNELING,
    DATA_KNX_CONFIG,
    DOMAIN,
    KNX_ADDRESS,
    SupportedPlatforms,
)
from .expose import KNXExposeSensor, KNXExposeTime, create_knx_exposure
from .schema import (
    BinarySensorSchema,
    ClimateSchema,
    ConnectionSchema,
    CoverSchema,
    EventSchema,
    ExposeSchema,
    FanSchema,
    LightSchema,
    NotifySchema,
    NumberSchema,
    SceneSchema,
    SelectSchema,
    SensorSchema,
    SwitchSchema,
    WeatherSchema,
    ga_validator,
    sensor_type_validator,
)

_LOGGER = logging.getLogger(__name__)


CONF_KNX_FIRE_EVENT: Final = "fire_event"
CONF_KNX_EVENT_FILTER: Final = "event_filter"

SERVICE_KNX_SEND: Final = "send"
SERVICE_KNX_ATTR_PAYLOAD: Final = "payload"
SERVICE_KNX_ATTR_TYPE: Final = "type"
SERVICE_KNX_ATTR_REMOVE: Final = "remove"
SERVICE_KNX_EVENT_REGISTER: Final = "event_register"
SERVICE_KNX_EXPOSURE_REGISTER: Final = "exposure_register"
SERVICE_KNX_READ: Final = "read"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            # deprecated since 2021.12
            cv.deprecated(CONF_KNX_ROUTING),
            cv.deprecated(CONF_KNX_TUNNELING),
            cv.deprecated(CONF_KNX_INDIVIDUAL_ADDRESS),
            cv.deprecated(ConnectionSchema.CONF_KNX_MCAST_GRP),
            cv.deprecated(ConnectionSchema.CONF_KNX_MCAST_PORT),
            cv.deprecated(CONF_KNX_EVENT_FILTER),
            # deprecated since 2021.4
            cv.deprecated("config_file"),
            # deprecated since 2021.2
            cv.deprecated(CONF_KNX_FIRE_EVENT),
            cv.deprecated("fire_event_filter", replacement_key=CONF_KNX_EVENT_FILTER),
            vol.Schema(
                {
                    **ConnectionSchema.SCHEMA,
                    vol.Optional(CONF_KNX_FIRE_EVENT): cv.boolean,
                    vol.Optional(CONF_KNX_EVENT_FILTER, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    **EventSchema.SCHEMA,
                    **ExposeSchema.platform_node(),
                    **BinarySensorSchema.platform_node(),
                    **ClimateSchema.platform_node(),
                    **CoverSchema.platform_node(),
                    **FanSchema.platform_node(),
                    **LightSchema.platform_node(),
                    **NotifySchema.platform_node(),
                    **NumberSchema.platform_node(),
                    **SceneSchema.platform_node(),
                    **SelectSchema.platform_node(),
                    **SensorSchema.platform_node(),
                    **SwitchSchema.platform_node(),
                    **WeatherSchema.platform_node(),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_KNX_SEND_SCHEMA = vol.Any(
    vol.Schema(
        {
            vol.Required(KNX_ADDRESS): vol.All(
                cv.ensure_list,
                [ga_validator],
            ),
            vol.Required(SERVICE_KNX_ATTR_PAYLOAD): cv.match_all,
            vol.Required(SERVICE_KNX_ATTR_TYPE): sensor_type_validator,
        }
    ),
    vol.Schema(
        # without type given payload is treated as raw bytes
        {
            vol.Required(KNX_ADDRESS): vol.All(
                cv.ensure_list,
                [ga_validator],
            ),
            vol.Required(SERVICE_KNX_ATTR_PAYLOAD): vol.Any(
                cv.positive_int, [cv.positive_int]
            ),
        }
    ),
)

SERVICE_KNX_READ_SCHEMA = vol.Schema(
    {
        vol.Required(KNX_ADDRESS): vol.All(
            cv.ensure_list,
            [ga_validator],
        )
    }
)

SERVICE_KNX_EVENT_REGISTER_SCHEMA = vol.Schema(
    {
        vol.Required(KNX_ADDRESS): vol.All(
            cv.ensure_list,
            [ga_validator],
        ),
        vol.Optional(CONF_TYPE): sensor_type_validator,
        vol.Optional(SERVICE_KNX_ATTR_REMOVE, default=False): cv.boolean,
    }
)

SERVICE_KNX_EXPOSURE_REGISTER_SCHEMA = vol.Any(
    ExposeSchema.EXPOSE_SENSOR_SCHEMA.extend(
        {
            vol.Optional(SERVICE_KNX_ATTR_REMOVE, default=False): cv.boolean,
        }
    ),
    vol.Schema(
        # for removing only `address` is required
        {
            vol.Required(KNX_ADDRESS): ga_validator,
            vol.Required(SERVICE_KNX_ATTR_REMOVE): vol.All(cv.boolean, True),
        },
        extra=vol.ALLOW_EXTRA,
    ),
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Start the KNX integration."""
    conf: ConfigType | None = config.get(DOMAIN)

    if conf is None:
        # If we have a config entry, setup is done by that config entry.
        # If there is no config entry, this should fail.
        return bool(hass.config_entries.async_entries(DOMAIN))

    conf = dict(conf)

    hass.data[DATA_KNX_CONFIG] = conf

    # Only import if we haven't before.
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    conf = hass.data.get(DATA_KNX_CONFIG)

    #  When reloading
    if conf is None:
        conf = await async_integration_yaml_config(hass, DOMAIN)
        if not conf or DOMAIN not in conf:
            return False

        conf = conf[DOMAIN]
        hass.data[DATA_KNX_CONFIG] = conf

    # If user didn't have configuration.yaml config, generate defaults
    if conf is None:
        conf = CONFIG_SCHEMA({DOMAIN: dict(entry.data)})[DOMAIN]

    config = {**entry.data, **conf}

    try:
        knx_module = KNXModule(hass, config, entry)
        await knx_module.start()
    except XKNXException as ex:
        raise ConfigEntryNotReady from ex

    hass.data[DOMAIN] = knx_module

    if CONF_KNX_EXPOSE in config:
        for expose_config in config[CONF_KNX_EXPOSE]:
            knx_module.exposures.append(
                create_knx_exposure(hass, knx_module.xknx, expose_config)
            )

    async def setup_platforms() -> None:
        """Set up platforms."""
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_setup(entry, platform.value)
                for platform in SupportedPlatforms
                if platform.value in config
            )
        )

    hass.async_create_task(setup_platforms())

    # set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    if NotifySchema.PLATFORM_NAME in conf:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, "notify", DOMAIN, conf[NotifySchema.PLATFORM_NAME], config
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_KNX_SEND,
        knx_module.service_send_to_knx_bus,
        schema=SERVICE_KNX_SEND_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_KNX_READ,
        knx_module.service_read_to_knx_bus,
        schema=SERVICE_KNX_READ_SCHEMA,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_KNX_EVENT_REGISTER,
        knx_module.service_event_register_modify,
        schema=SERVICE_KNX_EVENT_REGISTER_SCHEMA,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_KNX_EXPOSURE_REGISTER,
        knx_module.service_exposure_register_modify,
        schema=SERVICE_KNX_EXPOSURE_REGISTER_SCHEMA,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the KNX platforms."""
    knx_module: KNXModule = hass.data[DOMAIN]
    for exposure in knx_module.exposures:
        exposure.shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        [
            platform.value
            for platform in SupportedPlatforms
            if platform.value in hass.data[DATA_KNX_CONFIG]
        ],
    )
    if unload_ok:
        await knx_module.stop()
        hass.data[DOMAIN] = None
        hass.data[DATA_KNX_CONFIG] = None

    return unload_ok


class KNXModule:
    """Representation of KNX Object."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigType, entry: ConfigEntry
    ) -> None:
        """Initialize KNX module."""
        self.hass = hass
        self.config = config
        self.connected = False
        self.exposures: list[KNXExposeSensor | KNXExposeTime] = []
        self.service_exposures: dict[str, KNXExposeSensor | KNXExposeTime] = {}
        self.entry = entry

        self.init_xknx()
        self.xknx.connection_manager.register_connection_state_changed_cb(
            self.connection_state_changed_cb
        )

        self._address_filter_transcoder: dict[AddressFilter, type[DPTBase]] = {}
        self._group_address_transcoder: dict[DeviceGroupAddress, type[DPTBase]] = {}
        self._knx_event_callback: TelegramQueue.Callback = (
            self.register_event_callback()
        )

        self.entry.async_on_unload(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)
        )

    def init_xknx(self) -> None:
        """Initialize XKNX object."""
        self.xknx = XKNX(
            own_address=self.config[CONF_KNX_INDIVIDUAL_ADDRESS],
            rate_limit=self.config[ConnectionSchema.CONF_KNX_RATE_LIMIT],
            multicast_group=self.config[ConnectionSchema.CONF_KNX_MCAST_GRP],
            multicast_port=self.config[ConnectionSchema.CONF_KNX_MCAST_PORT],
            connection_config=self.connection_config(),
            state_updater=self.config[ConnectionSchema.CONF_KNX_STATE_UPDATER],
        )

    async def start(self) -> None:
        """Start XKNX object. Connect to tunneling or Routing device."""
        await self.xknx.start()

    async def stop(self, event: Event | None = None) -> None:
        """Stop XKNX object. Disconnect from tunneling or Routing device."""
        await self.xknx.stop()

    def connection_config(self) -> ConnectionConfig:
        """Return the connection_config."""
        _conn_type: str = self.config[CONF_KNX_CONNECTION_TYPE]
        if _conn_type == CONF_KNX_ROUTING:
            return ConnectionConfig(
                connection_type=ConnectionType.ROUTING,
                auto_reconnect=True,
            )
        if _conn_type == CONF_KNX_TUNNELING:
            return ConnectionConfig(
                connection_type=ConnectionType.TUNNELING,
                gateway_ip=self.config[CONF_HOST],
                gateway_port=self.config[CONF_PORT],
                route_back=self.config.get(ConnectionSchema.CONF_KNX_ROUTE_BACK, False),
                auto_reconnect=True,
            )

        return ConnectionConfig(auto_reconnect=True)

    async def connection_state_changed_cb(self, state: XknxConnectionState) -> None:
        """Call invoked after a KNX connection state change was received."""
        self.connected = state == XknxConnectionState.CONNECTED
        if tasks := [device.after_update() for device in self.xknx.devices]:
            await asyncio.gather(*tasks)

    async def telegram_received_cb(self, telegram: Telegram) -> None:
        """Call invoked after a KNX telegram was received."""
        # Not all telegrams have serializable data.
        data: int | tuple[int, ...] | None = None
        value = None
        if (
            isinstance(telegram.payload, (GroupValueWrite, GroupValueResponse))
            and telegram.payload.value is not None
            and isinstance(
                telegram.destination_address, (GroupAddress, InternalGroupAddress)
            )
        ):
            data = telegram.payload.value.value

            if isinstance(data, tuple):
                if transcoder := (
                    self._group_address_transcoder.get(telegram.destination_address)
                    or next(
                        (
                            _transcoder
                            for _filter, _transcoder in self._address_filter_transcoder.items()
                            if _filter.match(telegram.destination_address)
                        ),
                        None,
                    )
                ):
                    try:
                        value = transcoder.from_knx(data)
                    except ConversionError as err:
                        _LOGGER.warning(
                            "Error in `knx_event` at decoding type '%s' from telegram %s\n%s",
                            transcoder.__name__,
                            telegram,
                            err,
                        )

        self.hass.bus.async_fire(
            "knx_event",
            {
                "data": data,
                "destination": str(telegram.destination_address),
                "direction": telegram.direction.value,
                "value": value,
                "source": str(telegram.source_address),
                "telegramtype": telegram.payload.__class__.__name__,
            },
        )

    def register_event_callback(self) -> TelegramQueue.Callback:
        """Register callback for knx_event within XKNX TelegramQueue."""
        # backwards compatibility for deprecated CONF_KNX_EVENT_FILTER
        # use `address_filters = []` when this is not needed anymore
        address_filters = list(
            map(AddressFilter, self.config[DOMAIN][CONF_KNX_EVENT_FILTER])
        )
        for filter_set in self.config[DOMAIN][CONF_EVENT]:
            _filters = list(map(AddressFilter, filter_set[KNX_ADDRESS]))
            address_filters.extend(_filters)
            if (dpt := filter_set.get(CONF_TYPE)) and (
                transcoder := DPTBase.parse_transcoder(dpt)
            ):
                self._address_filter_transcoder.update(
                    {_filter: transcoder for _filter in _filters}  # type: ignore[misc]
                )

        return self.xknx.telegram_queue.register_telegram_received_cb(
            self.telegram_received_cb,
            address_filters=address_filters,
            group_addresses=[],
            match_for_outgoing=True,
        )

    async def service_event_register_modify(self, call: ServiceCall) -> None:
        """Service for adding or removing a GroupAddress to the knx_event filter."""
        attr_address = call.data[KNX_ADDRESS]
        group_addresses = list(map(parse_device_group_address, attr_address))

        if call.data.get(SERVICE_KNX_ATTR_REMOVE):
            for group_address in group_addresses:
                try:
                    self._knx_event_callback.group_addresses.remove(group_address)
                except ValueError:
                    _LOGGER.warning(
                        "Service event_register could not remove event for '%s'",
                        str(group_address),
                    )
                if group_address in self._group_address_transcoder:
                    del self._group_address_transcoder[group_address]
            return

        if (dpt := call.data.get(CONF_TYPE)) and (
            transcoder := DPTBase.parse_transcoder(dpt)
        ):
            self._group_address_transcoder.update(
                {_address: transcoder for _address in group_addresses}  # type: ignore[misc]
            )
        for group_address in group_addresses:
            if group_address in self._knx_event_callback.group_addresses:
                continue
            self._knx_event_callback.group_addresses.append(group_address)
            _LOGGER.debug(
                "Service event_register registered event for '%s'",
                str(group_address),
            )

    async def service_exposure_register_modify(self, call: ServiceCall) -> None:
        """Service for adding or removing an exposure to KNX bus."""
        group_address = call.data[KNX_ADDRESS]

        if call.data.get(SERVICE_KNX_ATTR_REMOVE):
            try:
                removed_exposure = self.service_exposures.pop(group_address)
            except KeyError as err:
                raise HomeAssistantError(
                    f"Could not find exposure for '{group_address}' to remove."
                ) from err
            else:
                removed_exposure.shutdown()
            return

        if group_address in self.service_exposures:
            replaced_exposure = self.service_exposures.pop(group_address)
            _LOGGER.warning(
                "Service exposure_register replacing already registered exposure for '%s' - %s",
                group_address,
                replaced_exposure.device.name,
            )
            replaced_exposure.shutdown()
        exposure = create_knx_exposure(self.hass, self.xknx, call.data)  # type: ignore[arg-type]
        self.service_exposures[group_address] = exposure
        _LOGGER.debug(
            "Service exposure_register registered exposure for '%s' - %s",
            group_address,
            exposure.device.name,
        )

    async def service_send_to_knx_bus(self, call: ServiceCall) -> None:
        """Service for sending an arbitrary KNX message to the KNX bus."""
        attr_address = call.data[KNX_ADDRESS]
        attr_payload = call.data[SERVICE_KNX_ATTR_PAYLOAD]
        attr_type = call.data.get(SERVICE_KNX_ATTR_TYPE)

        payload: DPTBinary | DPTArray
        if attr_type is not None:
            transcoder = DPTBase.parse_transcoder(attr_type)
            if transcoder is None:
                raise ValueError(f"Invalid type for knx.send service: {attr_type}")
            payload = DPTArray(transcoder.to_knx(attr_payload))
        elif isinstance(attr_payload, int):
            payload = DPTBinary(attr_payload)
        else:
            payload = DPTArray(attr_payload)

        for address in attr_address:
            telegram = Telegram(
                destination_address=parse_device_group_address(address),
                payload=GroupValueWrite(payload),
            )
            await self.xknx.telegrams.put(telegram)

    async def service_read_to_knx_bus(self, call: ServiceCall) -> None:
        """Service for sending a GroupValueRead telegram to the KNX bus."""
        for address in call.data[KNX_ADDRESS]:
            telegram = Telegram(
                destination_address=parse_device_group_address(address),
                payload=GroupValueRead(),
            )
            await self.xknx.telegrams.put(telegram)
