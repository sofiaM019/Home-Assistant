"""Component to manage a shopping list."""
import asyncio
import logging
import uuid
import json
from homeassistant.core import callback
from homeassistant.helpers import intent
from homeassistant.util.json import load_json, save_json
import homeassistant.ais_dom.ais_global as ais_global

DOMAIN = 'ais_bookmarks'
DEPENDENCIES = ['http']
_LOGGER = logging.getLogger(__name__)
INTENT_ADD_FAVORITE = 'AisBookmarksAddFavorite'
INTENT_LAST_BOOKMARKS = 'AisBookmarksLastBookmarks'
INTENT_PLAY_LAST_BOOKMARK = 'AisBookmarkPlayLastBookmark'
PERSISTENCE_BOOKMARKS = '.dom/.ais_bookmarks.json'
PERSISTENCE_FAVORITES = '.dom/.ais_favorites.json'

SERVICE_ADD_BOOKMARK = 'add_bookmark'
SERVICE_ADD_FAVORITE = 'add_favorite'
SERVICE_GET_BOOKMARKS = 'get_bookmarks'
SERVICE_GET_FAVORITES = 'get_favorites'
SERVICE_PLAY_BOOKMARK = 'play_bookmark'
SERVICE_PLAY_FAVORITE = 'play_favorite'
SERVICE_DELETE_BOOKMARK = 'delete_bookmark'
SERVICE_DELETE_FAVORITE = 'delete_favorite'


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the ais bookmarks list."""
    @asyncio.coroutine
    def add_bookmark_service(call):
        """Add an current played item to bookmark"""
        d = hass.data[DOMAIN]
        d.async_add(call, True)

    @asyncio.coroutine
    def add_favorite_service(call):
        """Add an current played item to favorite."""
        d = hass.data[DOMAIN]
        d.async_add(call, False)

    @asyncio.coroutine
    def get_bookmarks_service(call):
        """Return the list of bookmarks to app list"""
        d = hass.data[DOMAIN]
        list_info = {}
        list_idx = 0
        for item in reversed(d.bookmarks):
            if "media_stream_image" in item and item["media_stream_image"] is not None:
                img = item["media_stream_image"]
            else:
                img = "/static/icons/tile-win-310x150.png"
            list_info[list_idx] = {}
            list_info[list_idx]["title"] = item['source'] + " " + item['name']
            list_info[list_idx]["name"] = item['source'] + " " + item['name']
            list_info[list_idx]["thumbnail"] = img
            list_info[list_idx]["uri"] = item["media_content_id"]
            list_info[list_idx]["mediasource"] = item['source']
            list_info[list_idx]["type"] = item['source']
            list_info[list_idx]["icon"] = 'mdi:bookmark-music'
            list_info[list_idx]["icon_remove"] = 'mdi:delete-forever'
            list_info[list_idx]["id"] = item['id']
            list_info[list_idx]["media_position"] = ais_global.get_milliseconds_formated(item['media_position'])
            list_idx = list_idx + 1
        # create lists
        hass.states.async_set("sensor.aisbookmarkslist", -1, list_info)

    @asyncio.coroutine
    def get_favorites_service(call):
        """Return the list of favorites to app list"""
        d = hass.data[DOMAIN]
        list_info = {}
        list_idx = 0
        for item in reversed(d.favorites):
            if "media_stream_image" in item and item["media_stream_image"] is not None:
                img = item["media_stream_image"]
            else:
                img = "/static/icons/tile-win-310x150.png"
            list_info[list_idx] = {}
            list_info[list_idx]["title"] = item['source'] + " " + item['name']
            list_info[list_idx]["name"] = item['source'] + " " + item['name']
            list_info[list_idx]["thumbnail"] = img
            list_info[list_idx]["uri"] = item["media_content_id"]
            list_info[list_idx]["mediasource"] = ais_global.G_AN_FAVORITE
            list_info[list_idx]["type"] = item['source']
            list_info[list_idx]["icon_type"] = ais_global.G_ICON_FOR_AUDIO.get(item['source'], 'mdi:play')
            list_info[list_idx]["icon_remove"] = 'mdi:delete-forever'
            list_info[list_idx]["icon"] = 'mdi:play'
            list_info[list_idx]["id"] = item['id']
            list_idx = list_idx + 1
        # create lists
        hass.states.async_set("sensor.aisfavoriteslist", -1, list_info)


    @asyncio.coroutine
    def play_bookmark_service(call):
        """Play selected bookmark"""
        bookmark_id = int(call.data.get("id"))
        # get item from list
        state = hass.states.get("sensor.aisbookmarkslist")
        attr = state.attributes
        track = attr.get(bookmark_id)
        _audio_info = json.dumps({"IMAGE_URL": track["thumbnail"], "NAME": track['name'],
                                  "MEDIA_SOURCE": track['type'],"media_content_id": track['uri']})
        # set stream uri, image and title
        hass.async_add_job(
            hass.services.async_call(
                'media_player',
                'play_media', {
                    "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                    "media_content_type": "ais_content_info",
                    "media_content_id": _audio_info
                })
        )

    @asyncio.coroutine
    def play_favorite_service(call):
        """Play selected favorite"""
        favorite_id = int(call.data.get("id"))
        # get item from list
        state = hass.states.get("sensor.aisfavoriteslist")
        attr = state.attributes
        track = attr.get(favorite_id)

        _audio_info = json.dumps({"IMAGE_URL": track["thumbnail"], "NAME": track['name'], "ais_list_id": favorite_id,
                                  "MEDIA_SOURCE": ais_global.G_AN_FAVORITE, "media_content_id": track['uri']})
        # set stream uri, image and title
        hass.async_add_job(
            hass.services.async_call(
                'media_player',
                'play_media', {
                    "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                    "media_content_type": "ais_content_info",
                    "media_content_id": _audio_info
                })
        )

    @asyncio.coroutine
    def delete_bookmark_service(call):
        """Delete selected bookmark"""
        bookmark_id = int(call.data.get("id"))
        state = hass.states.get('sensor.aisbookmarkslist')
        attr = state.attributes
        track = attr.get(bookmark_id)
        d = hass.data[DOMAIN]
        d.async_remove_bookmark(track['id'], True)

    @asyncio.coroutine
    def delete_favorite_service(call):
        """Delete selected favorite"""
        favorite_id = int(call.data.get("id"))
        state = hass.states.get('sensor.aisfavoriteslist')
        attr = state.attributes
        track = attr.get(favorite_id)
        d = hass.data[DOMAIN]
        d.async_remove_bookmark(track['id'], False)

    data = hass.data[DOMAIN] = BookmarksData(hass)
    intent.async_register(hass, AddFavoriteIntent())
    intent.async_register(hass, ListTopBookmarkIntent())
    intent.async_register(hass, PlayLastBookmarkIntent())
    hass.services.async_register(DOMAIN, SERVICE_ADD_BOOKMARK, add_bookmark_service)
    hass.services.async_register(DOMAIN, SERVICE_ADD_FAVORITE, add_favorite_service)
    hass.services.async_register(DOMAIN, SERVICE_GET_BOOKMARKS, get_bookmarks_service)
    hass.services.async_register(DOMAIN, SERVICE_GET_FAVORITES, get_favorites_service)
    hass.services.async_register(DOMAIN, SERVICE_PLAY_BOOKMARK, play_bookmark_service)
    hass.services.async_register(DOMAIN, SERVICE_PLAY_FAVORITE, play_favorite_service)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_BOOKMARK, delete_bookmark_service)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_FAVORITE, delete_favorite_service)

    hass.components.conversation.async_register(INTENT_ADD_FAVORITE, [
        'Dodaj do ulubionych',
        'Do ulubionych',
        'Lubię to',
    ])
    hass.components.conversation.async_register(INTENT_LAST_BOOKMARKS, [
        'Jakie mam zakładki', 'Jakie są zakładki'
    ])
    hass.components.conversation.async_register(INTENT_PLAY_LAST_BOOKMARK, [
        'Włącz ostatnią zakładkę', 'Włącz zakładkę', 'Ostatnia zakładka'
    ])

    yield from data.async_load()

    hass.states.async_set("sensor.aisbookmarkslist", -1, {})
    hass.states.async_set("sensor.aisfavoriteslist", -1, {})

    return True


class BookmarksData:
    """Class to hold bookmarks list data."""

    def __init__(self, hass):
        """Initialize the bookmarks list."""
        self.hass = hass
        self.bookmarks = []
        self.favorites = []

    @callback
    def async_add(self, call, bookmark):
        """Add a item."""
        attributes = {}
        if "attr" in call.data:
            attributes = call.data["attr"]
            name = attributes.get("media_title").strip()
            source = attributes.get("source").strip()
            media_position = attributes.get("media_position", None)
            media_content_id = attributes.get("media_content_id")
        else:
            state = self.hass.states.get(ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID)
            attributes = state.attributes
            name = attributes.get("media_title")
            source = attributes.get("source")
            media_position = attributes.get("media_position", None)
            media_content_id = attributes.get("media_content_id")
        try:
            media_stream_image = ais_global.G_CURR_MEDIA_CONTENT["IMAGE_URL"]
        except Exception:
            media_stream_image = "/static/icons/favicon-100x100.png"

        if name is None or source is None or media_content_id is None:
            _LOGGER.warning("can't add the bookmark, no full info provided " + str(attributes))
            return

        if bookmark:
            # type validation
            if source not in (ais_global.G_AN_SPOTIFY, ais_global.G_AN_MUSIC, ais_global.G_AN_LOCAL,
                              ais_global.G_AN_PODCAST, ais_global.G_AN_RADIO):
                source_pl = ais_global.G_ICON_FOR_AUDIO.get(source, '')
                message = "Nie można dodać zakładki do".format(source_pl, name)
                self.hass.async_add_job(self.hass.services.async_call('ais_ai_service', 'say_it', {"text": message}))
                return

            # check if the audio is on bookmark list
            item = next((itm for itm in self.bookmarks if (itm['name'] == name and itm['source'] == source)), None)
            if item is not None:
                # delete the old bookmark
                self.async_remove_bookmark(item['id'], True)
            # add the bookmark
            item = {
                'name': name,
                'id': uuid.uuid4().hex,
                'source': source,
                'media_position': media_position,
                'media_content_id': media_content_id,
                'media_stream_image': media_stream_image
            }
            self.bookmarks.append(item)
            self.hass.async_add_job(self.save, True)
            return item
        else:
            # type validation
            if source == ais_global.G_AN_FAVORITE:
                source_pl = ais_global.G_NAME_FOR_AUDIO.get(source, 'Pozycja')
                message = "{}, {} jest już w ulubionych.".format(source_pl, name)
                self.hass.async_add_job(self.hass.services.async_call('ais_ai_service', 'say_it', {"text": message}))
                return
            # if podcast then we will add not track but audition
            if source == ais_global.G_AN_PODCAST:
                media_content_id = ais_global.G_CURR_MEDIA_CONTENT["lookup_url"]
                name = ais_global.G_CURR_MEDIA_CONTENT["lookup_name"]

            # check if the audio is on favorites list
            item = next((itm for itm in self.favorites if (itm['name'] == name and itm['source'] == source)), None)
            if item is not None:
                message = '{}, {} jest już w ulubionych.'.format(source, name)
                self.hass.async_add_job(self.hass.services.async_call('ais_ai_service', 'say_it', {"text": message}))
                return
            # add item
            item = {
                'name': name,
                'id': uuid.uuid4().hex,
                'source': source,
                'media_content_id': media_content_id,
                'media_stream_image': media_stream_image
            }
            self.favorites.append(item)
            self.hass.async_add_job(self.save, False)
            message = "Dobrze zapamiętam - dodaje {} {} do Twoich ulubionych".format(source, name)
            self.hass.async_add_job(self.hass.services.async_call('ais_ai_service', 'say_it', {"text": message}))
            return item

    @callback
    def async_update(self, item_id, info):
        """Update a bookmarks list item."""
        item = next((itm for itm in self.bookmarks if itm['id'] == item_id), None)

        if item is None:
            raise KeyError

        item.update(info)
        self.hass.async_add_job(self.save)
        return item

    @callback
    def async_remove_bookmark(self, item_id, bookmark):
        if bookmark:
            """Reemove bookmark """
            self.bookmarks = [itm for itm in self.bookmarks if not itm['id'] == item_id]
            self.hass.async_add_job(self.save, True)
        else:
            """Reemove favorites """
            self.favorites = [itm for itm in self.favorites if not itm['id'] == item_id]
            self.hass.async_add_job(self.save, False)


    @asyncio.coroutine
    def async_load(self):
        """Load bookmarks."""
        def load():
            """Load the bookmarks synchronously."""
            try:
                self.bookmarks = load_json(self.hass.config.path(PERSISTENCE_BOOKMARKS), default=[])
                self.favorites = load_json(self.hass.config.path(PERSISTENCE_FAVORITES), default=[])
            except Exception as e:
                _LOGGER.error("Can't load bookmarks data: " + str(e))
        yield from self.hass.async_add_job(load)

    def save(self, bookmark):
        """Save the bookmarks and favorites."""
        if bookmark:
            self.bookmarks = self.bookmarks[-50:]
            save_json(self.hass.config.path(PERSISTENCE_BOOKMARKS), self.bookmarks)
            self.hass.async_add_job(self.hass.services.async_call(DOMAIN, SERVICE_GET_BOOKMARKS))
        else:
            self.favorites = self.favorites[-50:]
            save_json(self.hass.config.path(PERSISTENCE_FAVORITES), self.favorites)
            self.hass.async_add_job(self.hass.services.async_call(DOMAIN, SERVICE_GET_FAVORITES))


class AddFavoriteIntent(intent.IntentHandler):
    """Handle AddItem intents."""
    intent_type = INTENT_ADD_FAVORITE

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        state = hass.states.get('media_player.wbudowany_glosnik')
        name = state.attributes.get("media_title")
        source = state.attributes.get("source")
        media_content_id = state.attributes.get("media_content_id")
        # check if all fields are provided
        if name is None or source is None or media_content_id is None:
            answer = "Nie można dodać do ulubionych - brak informacji o odtwarzanym audio."
        else:
            answer = "Dobrze zapamiętam - dodaje {} do Twoich ulubionych".format(name)
            hass.data[DOMAIN].async_add(state.attributes, False)
        response = intent_obj.create_response()
        response.async_set_speech(answer)
        return response


class ListTopBookmarkIntent(intent.IntentHandler):
    """Handle ListTopBookmarkIntent intents."""

    intent_type = INTENT_LAST_BOOKMARKS

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        bookmarks = intent_obj.hass.data[DOMAIN].bookmarks[-5:]
        response = intent_obj.create_response()
        if not bookmarks:
            answer = "Nie ma żadnych zakładek"
        else:
            answer = "Oto ostatnie {} zakładki na twojej liście: {}".format(
                        min(len(bookmarks), 5),
                        ', '.join(itm['name'] for itm in reversed(bookmarks)))
        response.async_set_speech(answer)
        yield from hass.services.async_call('ais_ai_service', 'say_it', {"text": answer})
        return response


class PlayLastBookmarkIntent(intent.IntentHandler):
    """Handle PlayLastBookmarkIntent intents."""

    intent_type = INTENT_PLAY_LAST_BOOKMARK

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        bookmarks = intent_obj.hass.data[DOMAIN].bookmarks[-1:]
        response = intent_obj.create_response()
        if not bookmarks:
            answer = "Nie ma żadnych zakładek"
        else:
            bookmark = bookmarks[0]["source"] + '; ' + bookmarks[0]["name"]
            answer = "Włączam ostatnią zakładkę {}".format(bookmark)
            yield from hass.services.async_call('ais_bookmarks', 'play_bookmark', {"bookmark": bookmark})
        response.async_set_speech(answer)
        yield from hass.services.async_call('ais_ai_service', 'say_it', {"text": answer})
        return response
