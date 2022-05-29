"""Support for local control of entities by emulating a Philips Hue bridge."""
from __future__ import annotations

import logging

from aiohttp import web
import voluptuous as vol

from homeassistant.components.network import async_get_source_ip
from homeassistant.const import (
    CONF_ENTITIES,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .config import (
    CONF_ADVERTISE_IP,
    CONF_ADVERTISE_PORT,
    CONF_ENTITY_HIDDEN,
    CONF_ENTITY_NAME,
    CONF_EXPOSE_BY_DEFAULT,
    CONF_EXPOSED_DOMAINS,
    CONF_HOST_IP,
    CONF_LIGHTS_ALL_DIMMABLE,
    CONF_LISTEN_PORT,
    CONF_OFF_MAPS_TO_ON_DOMAINS,
    CONF_UPNP_BIND_MULTICAST,
    DEFAULT_LIGHTS_ALL_DIMMABLE,
    DEFAULT_LISTEN_PORT,
    DEFAULT_TYPE,
    TYPE_ALEXA,
    TYPE_GOOGLE,
    Config,
)
from .const import DOMAIN
from .hue_api import (
    HueAllGroupsStateView,
    HueAllLightsStateView,
    HueConfigView,
    HueFullStateView,
    HueGroupView,
    HueOneLightChangeView,
    HueOneLightStateView,
    HueUnauthorizedUser,
    HueUsernameView,
)
from .upnp import (
    DescriptionXmlView,
    UPNPResponderProtocol,
    create_upnp_datagram_endpoint,
)

_LOGGER = logging.getLogger(__name__)


CONFIG_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ENTITY_NAME): cv.string,
        vol.Optional(CONF_ENTITY_HIDDEN): cv.boolean,
    }
)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST_IP): cv.string,
                vol.Optional(CONF_LISTEN_PORT, default=DEFAULT_LISTEN_PORT): cv.port,
                vol.Optional(CONF_ADVERTISE_IP): cv.string,
                vol.Optional(CONF_ADVERTISE_PORT): cv.port,
                vol.Optional(CONF_UPNP_BIND_MULTICAST): cv.boolean,
                vol.Optional(CONF_OFF_MAPS_TO_ON_DOMAINS): cv.ensure_list,
                vol.Optional(CONF_EXPOSE_BY_DEFAULT): cv.boolean,
                vol.Optional(CONF_EXPOSED_DOMAINS): cv.ensure_list,
                vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): vol.Any(
                    TYPE_ALEXA, TYPE_GOOGLE
                ),
                vol.Optional(CONF_ENTITIES): vol.Schema(
                    {cv.entity_id: CONFIG_ENTITY_SCHEMA}
                ),
                vol.Optional(
                    CONF_LIGHTS_ALL_DIMMABLE, default=DEFAULT_LIGHTS_ALL_DIMMABLE
                ): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    """Activate the emulated_hue component."""
    local_ip = await async_get_source_ip(hass)
    config = Config(hass, yaml_config.get(DOMAIN, {}), local_ip)
    await config.async_setup()

    app = web.Application()
    app["hass"] = hass

    # We misunderstood the startup signal. You're not allowed to change
    # anything during startup. Temp workaround.
    # pylint: disable=protected-access
    app._on_startup.freeze()
    await app.startup()

    runner = None
    site = None

    DescriptionXmlView(config).register(app, app.router)
    HueUsernameView().register(app, app.router)
    HueConfigView(config).register(app, app.router)
    HueUnauthorizedUser().register(app, app.router)
    HueAllLightsStateView(config).register(app, app.router)
    HueOneLightStateView(config).register(app, app.router)
    HueOneLightChangeView(config).register(app, app.router)
    HueAllGroupsStateView(config).register(app, app.router)
    HueGroupView(config).register(app, app.router)
    HueFullStateView(config).register(app, app.router)

    listen = create_upnp_datagram_endpoint(
        config.host_ip_addr,
        config.upnp_bind_multicast,
        config.advertise_ip,
        config.advertise_port or config.listen_port,
    )
    protocol: UPNPResponderProtocol | None = None

    async def stop_emulated_hue_bridge(event):
        """Stop the emulated hue bridge."""
        nonlocal protocol
        nonlocal site
        nonlocal runner

        if protocol:
            protocol.close()
        if site:
            await site.stop()
        if runner:
            await runner.cleanup()

    async def start_emulated_hue_bridge(event):
        """Start the emulated hue bridge."""
        nonlocal protocol
        nonlocal site
        nonlocal runner

        transport_protocol = await listen
        protocol = transport_protocol[1]

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, config.host_ip_addr, config.listen_port)

        try:
            await site.start()
        except OSError as error:
            _LOGGER.error(
                "Failed to create HTTP server at port %d: %s", config.listen_port, error
            )
            if protocol:
                protocol.close()
        else:
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, stop_emulated_hue_bridge
            )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_emulated_hue_bridge)

    return True
