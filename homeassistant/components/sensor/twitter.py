"""
Support for Twitter.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.twitter/
"""
from datetime import timedelta
import json
import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_NAME, ATTR_USERNAME,# TODO: Add attributes 
    CONF_ACCESS_TOKEN, CONF_USERNAME, CONF_NAME, CONF_PATH)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['TwitterAPI==2.5.9']

_LOGGER = logging.getLogger(__name__)

CONF_CONSUMER_KEY = 'consumer_key'
CONF_CONSUMER_SECRET = 'consumer_secret'
CONF_ACCESS_TOKEN_SECRET = 'access_token_secret'
CONF_USERNAMES = 'usernames'

DEFAULT_NAME = 'Twitter'

SCAN_INTERVAL = timedelta(seconds=300)

USERNAMES_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Required(CONF_ACCESS_TOKEN_SECRET): cv.string,
    vol.Required(CONF_CONSUMER_KEY): cv.string,
    vol.Required(CONF_CONSUMER_SECRET): cv.string,
    vol.Required(CONF_REPOS):
        vol.All(cv.ensure_list, [USERNAMES_SCHEMA])
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Twitter sensor platform."""
    sensors = []
    for username in config.get(CONF_USERNAMES):
        data = TwitterData(
            name=config.get(CONF_NAME),
            username=config.get(CONF_USERNAME),
            consumer_key=config.get(CONF_CONSUMER_KEY),
            consumer_secret=config.get(CONF_CONSUMER_SECRET),
            access_token_key=config.get(CONF_ACCESS_TOKEN),
            access_token_secret=config.get(CONF_ACCESS_TOKEN_SECRET)
        )
        sensors.append(TwitterSensor(data))
    add_entities(sensors, True)


class TwitterSensor(Entity):
    """Representation of a Twitter sensor."""

    def __init__(self, twitter_data):
        """Initialize the Twitter sensor."""
        self._unique_id = twitter_data.username
        self._name = None
        self._state = None
        self._available = False
        self._twitter_data = twitter_data
        self._latest_tweet_date = None
        self._latest_tweet_text = None
        self._latest_tweet_retweets = None
        self._latest_tweet_likes = None
        self._latest_tweet_hashtags = None
        self._latest_tweet_mentions = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID for the sensor."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_USERNAME: self._username# TODO: Add attributes
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:twitter-circle'

    def update(self):
        """Collect updated data from Twitter API."""
        self._twitter_data.update()

        self._name = self._twitter_data.name
        self._username = self._twitter_data.username
        self._state = self._twitter_data.latest_tweet_date
        self._available = self._twitter_data.available
        self._latest_tweet_date = self._twitter_data.latest_tweet_date
        self._latest_tweet_text = self._twitter_data.latest_tweet_text
        self._latest_tweet_retweets = self._twitter_data.latest_tweet_retweets
        self._latest_tweet_likes = self._twitter_data.latest_tweet_likes
        self._latest_tweet_hashtags = self._twitter_data.latest_tweet_hashtags
        self._latest_tweet_mentions = self._twitter_data.latest_tweet_mentions

class TwitterData():
    """Twitter Data object."""

    def __init__(self, name, username, consumer_key, consumer_secret, 
                 access_token_key, access_token_secret):
        """Set up Twitter."""
        from TwitterAPI import TwitterAPI

        self._api = TwitterAPI(consumer_key, consumer_secret,
                                   access_token_key, access_token_secret)

        self.name = name
        self.username = username

        self.available = False
        self.latest_tweet_date = None
        self.latest_tweet_text = None
        self.latest_tweet_retweets = None
        self.latest_tweet_likes = None
        self.latest_tweet_hashtags = None
        self.latest_tweet_mentions = None

    def update(self):
        """Update Twitter Sensor."""
        pager = TwitterPager(self._api,
                             'statuses/user_timeline',
                             { 'screen_name': self.username, 'count': 1 })

        tweet = pager.get_iterator(wait=3.5)[0]

        self.latest_tweet_date = tweet['created_at']
        self.latest_tweet_text = tweet['text']
        self.latest_tweet_retweets = tweet['retweet_count']
        self.latest_tweet_likes = tweet['favorite_count']
        self.latest_tweet_hashtags = json.dumps(tweet['entities']['hashtags'])
        mentions = []
        for user in tweet['entities']['user_mentions']:
            mentions.append(user['screen_name'])
        self.latest_tweet_mentions = json.dumps(mentions)

        self.available = True
