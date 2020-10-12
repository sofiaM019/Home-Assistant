"""Xbox Media Player Support."""
import logging
import re
from typing import List, Optional

from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.catalog.models import AlternateIdType, Image, Product
from xbox.webapi.api.provider.smartglass.models import (
    PlaybackState,
    PowerState,
    SmartglassConsole,
    SmartglassConsoleList,
    SmartglassConsoleStatus,
    VolumeDirection,
)

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_APP,
    MEDIA_TYPE_GAME,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)

from .const import APP_LEGACY_MAP, DOMAIN, HOME_LEGACY_PRODUCT_ID

_LOGGER = logging.getLogger(__name__)

SUPPORT_XBOX = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PLAY
    | SUPPORT_PAUSE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
)

XBOX_STATE_MAP = {
    PlaybackState.Playing: STATE_PLAYING,
    PlaybackState.Paused: STATE_PAUSED,
    PowerState.On: STATE_ON,
    PowerState.SystemUpdate: STATE_OFF,
    PowerState.ConnectedStandby: STATE_OFF,
    PowerState.Off: STATE_OFF,
    PowerState.Unknown: None,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Xbox media_player from a config entry."""
    client: XboxLiveClient = hass.data[DOMAIN][entry.entry_id]
    consoles: SmartglassConsoleList = await client.smartglass.get_console_list()
    async_add_entities(
        [XboxMediaPlayer(client, console) for console in consoles.result], True
    )


class XboxMediaPlayer(MediaPlayerEntity):
    """Representation of an Xbox device."""

    def __init__(self, client: XboxLiveClient, console: SmartglassConsole) -> None:
        """Initialize the Plex device."""
        self.client: XboxLiveClient = client
        self._console: SmartglassConsole = console

        self._console_status: SmartglassConsoleStatus = None
        self._app_details: Optional[Product] = None

    @property
    def name(self):
        """Return the device name."""
        return self._console.name

    @property
    def unique_id(self):
        """Console device ID."""
        return self._console.id

    @property
    def state(self):
        """State of the player."""
        if self._console_status.playback_state in XBOX_STATE_MAP:
            return XBOX_STATE_MAP[self._console_status.playback_state]
        return XBOX_STATE_MAP[self._console_status.power_state]

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        active_support = SUPPORT_XBOX
        if self.state not in [STATE_PLAYING, STATE_PAUSED]:
            active_support &= ~SUPPORT_NEXT_TRACK & ~SUPPORT_PREVIOUS_TRACK
        if not self._console_status.is_tv_configured:
            active_support &= ~SUPPORT_VOLUME_MUTE & ~SUPPORT_VOLUME_STEP
        return active_support

    @property
    def media_content_type(self):
        """Media content type."""
        if self._app_details and self._app_details.product_family == "Games":
            return MEDIA_TYPE_GAME
        return MEDIA_TYPE_APP

    @property
    def media_title(self):
        """Title of current playing media."""
        if not self._app_details:
        	return None
        return self._app_details.localized_properties[0].short_title

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if not self._app_details:
        	return None
        image = _find_media_image(self._app_details.localized_properties[0].images)

        if not image:
            return None

        url = image.uri
        if url[0] == "/":
            url = f"http:{url}"
        return url

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        return True

    async def async_update(self) -> None:
        """Update Xbox state."""
        status: SmartglassConsoleStatus = (
            await self.client.smartglass.get_console_status(self._console.id)
        )

        if status.focus_app_aumid:
            if (
                not self._console_status
                or status.focus_app_aumid != self._console_status.focus_app_aumid
            ):
                app_id = status.focus_app_aumid.split("!")[0]
                id_type = AlternateIdType.PACKAGE_FAMILY_NAME
                if app_id in APP_LEGACY_MAP:
                    app_id = APP_LEGACY_MAP[app_id]
                    id_type = AlternateIdType.LEGACY_XBOX_PRODUCT_ID
                catalog_result = (
                    await self.client.catalog.get_product_from_alternate_id(
                        app_id, id_type
                    )
                )
                if catalog_result and catalog_result.products:
                    self._app_details = catalog_result.products[0]
                else:
                    self._app_details = None
        else:
            if self.media_title != "Home":
                catalog_result = (
                    await self.client.catalog.get_product_from_alternate_id(
                        HOME_LEGACY_PRODUCT_ID, AlternateIdType.LEGACY_XBOX_PRODUCT_ID
                    )
                )
                self._app_details = catalog_result.products[0]

        self._console_status = status

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.client.smartglass.wake_up(self._console.id)

    async def async_turn_off(self):
        """Turn the media player off."""
        await self.client.smartglass.turn_off(self._console.id)

    async def async_mute_volume(self, mute):
        """Mute the volume."""
        await self.client.smartglass.mute(self._console.id)

    async def async_volume_up(self):
        """Turn volume up for media player."""
        await self.client.smartglass.volume(self._console.id, VolumeDirection.Up)

    async def async_volume_down(self):
        """Turn volume down for media player."""
        await self.client.smartglass.volume(self._console.id, VolumeDirection.Down)

    async def async_media_play(self):
        """Send play command."""
        await self.client.smartglass.play(self._console.id)

    async def async_media_pause(self):
        """Send pause command."""
        await self.client.smartglass.pause(self._console.id)

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self.client.smartglass.previous(self._console.id)

    async def async_media_next_track(self):
        """Send next track command."""
        await self.client.smartglass.next(self._console.id)

    @property
    def device_info(self):
        """Return a device description for device registry."""
        # Turns "XboxOneX" into "Xbox One X" for display
        matches = re.finditer(
            ".+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)",
            self._console.console_type,
        )
        model = " ".join([m.group(0) for m in matches])

        return {
            "identifiers": {(DOMAIN, self._console.id)},
            "name": self.name,
            "manufacturer": "Microsoft",
            "model": model,
        }


def _find_media_image(images=List[Image]) -> Optional[Image]:
    purpose_order = ["FeaturePromotionalSquareArt", "Logo", "BoxArt"]
    for purpose in purpose_order:
        for image in images:
            if image.image_purpose == purpose and image.width >= 300:
                return image
    return None
