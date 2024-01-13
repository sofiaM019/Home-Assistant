"""Teslemetry integration."""
import logging
from typing import Final

from tesla_fleet_api import Teslemetry
from tesla_fleet_api.exceptions import InvalidToken, TeslaFleetError
from tesla_fleet_api.vehiclespecific import VehicleSpecific
from teslemetry_stream import TeslemetryStream

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import TeslemetryVehicleDataCoordinator
from .models import TeslemetryVehicleData

PLATFORMS: Final = [
    Platform.CLIMATE,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Teslemetry config."""

    access_token = entry.data[CONF_ACCESS_TOKEN]

    # Create API connection
    api = Teslemetry(
        session=async_get_clientsession(hass),
        access_token=access_token,
    )
    try:
        products = (await api.products())["response"]
    except InvalidToken as e:
        raise ConfigEntryAuthFailed from e
    except TeslaFleetError as e:
        _LOGGER.error("Setup failed, unable to connect to Teslemetry: %s", e)
        return False

    # Setup Coordinator for Polling

    # Create SSE stream
    data = []
    for product in products:
        if "vin" not in product:
            continue
        vin = product["vin"]

        api = VehicleSpecific(api, vin)
        coordinator = TeslemetryVehicleDataCoordinator(hass, api)
        stream = TeslemetryStream(
            session=async_get_clientsession(hass),
            vin=vin,
            access_token=access_token,
        )
        data.append(
            TeslemetryVehicleData(api=api, coordinator=coordinator, stream=stream)
        )

    # Setup Platforms
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start SSE streams
    for vehicle in data:

        async def on_message(message):
            _LOGGER.debug("Received SSE message: %s", message)

        entry.async_create_background_task(
            hass, vehicle.stream.listen(on_message), vehicle.stream.vin
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Teslemetry Config."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Stop SSE streams
        for vehicle in hass.data[DOMAIN].pop(entry.entry_id):
            await vehicle.stream.close()

    return unload_ok
