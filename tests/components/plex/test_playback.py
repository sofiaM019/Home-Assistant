"""Tests for Plex player playback methods/services."""
from http import HTTPStatus
from unittest.mock import patch

import pytest

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MP_DOMAIN,
    MEDIA_TYPE_MOVIE,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError


class MockPlexMedia:
    """Minimal mock of plexapi media object."""

    key = "key"

    def __init__(self, title, mediatype):
        """Initialize the instance."""
        self.listType = mediatype
        self.title = title
        self.type = mediatype

    def section(self):
        """Return the LibrarySection."""
        return MockPlexLibrarySection()


class MockPlexLibrarySection:
    """Minimal mock of plexapi LibrarySection."""

    uuid = "00000000-0000-0000-0000-000000000000"


async def test_media_player_playback(
    hass,
    setup_plex_server,
    requests_mock,
    playqueue_created,
    player_plexweb_resources,
    caplog,
):
    """Test playing media on a Plex media_player."""
    requests_mock.get("http://1.2.3.5:32400/resources", text=player_plexweb_resources)

    await setup_plex_server()

    media_player = "media_player.plex_plex_web_chrome"
    requests_mock.post("/playqueues", text=playqueue_created)
    requests_mock.get("/player/playback/playMedia", status_code=HTTPStatus.OK)

    # Test media lookup failure
    payload = '{"library_name": "Movies", "title": "Movie 1" }'
    with patch("plexapi.library.LibrarySection.search", return_value=None):
        with pytest.raises(HomeAssistantError) as excinfo:
            assert await hass.services.async_call(
                MP_DOMAIN,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: media_player,
                    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MOVIE,
                    ATTR_MEDIA_CONTENT_ID: payload,
                },
                True,
            )
    assert f"Media could not be found: {payload}" in str(excinfo.value)

    # Test movie success
    movies = [MockPlexMedia("Movie 1", "movie")]
    with patch("plexapi.library.LibrarySection.search", return_value=movies):
        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MOVIE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies", "title": "Movie 1" }',
            },
            True,
        )

    # Test multiple choices with exact match
    movies = [MockPlexMedia("Movie", "movie"), MockPlexMedia("Movie II", "movie")]
    with patch("plexapi.library.LibrarySection.search", return_value=movies):
        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MOVIE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies", "title": "Movie" }',
            },
            True,
        )

    # Test multiple choices without exact match
    movies = [MockPlexMedia("Movie II", "movie"), MockPlexMedia("Movie III", "movie")]
    with pytest.raises(HomeAssistantError) as excinfo:
        payload = '{"library_name": "Movies", "title": "Movie" }'
        with patch("plexapi.library.LibrarySection.search", return_value=movies):
            assert await hass.services.async_call(
                MP_DOMAIN,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: media_player,
                    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MOVIE,
                    ATTR_MEDIA_CONTENT_ID: payload,
                },
                True,
            )
    assert f"Media could not be found: {payload}" in str(excinfo.value)
    assert "Multiple matches, make content_id more specific" in caplog.text
