"""
Stock market information from Alpha Vantage.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.alpha_vantage/
"""
from datetime import timedelta
from random import randint
from time import sleep
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    STATE_UNKNOWN, ATTR_ATTRIBUTION, CONF_API_KEY, CONF_CURRENCY, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['alpha_vantage==2.1.0']

_LOGGER = logging.getLogger(__name__)

ATTR_CLOSE = 'close'
ATTR_HIGH = 'high'
ATTR_LOW = 'low'

CONF_ATTRIBUTION = "Stock market information provided by Alpha Vantage"
CONF_FOREIGN_EXCHANGE = 'foreign_exchange'
CONF_FROM = 'from'
CONF_SYMBOL = 'symbol'
CONF_SYMBOLS = 'symbols'
CONF_TO = 'to'
CONF_CONVERT_CURRENCY = 'convert_currency'

ICONS = {
    'BTC': 'mdi:currency-btc',
    'EUR': 'mdi:currency-eur',
    'GBP': 'mdi:currency-gbp',
    'INR': 'mdi:currency-inr',
    'RUB': 'mdi:currency-rub',
    'TRY': 'mdi:currency-try',
    'USD': 'mdi:currency-usd',
}

SCAN_INTERVAL = timedelta(minutes=5)

SYMBOL_SCHEMA = vol.Schema({
    vol.Required(CONF_SYMBOL): cv.string,
    vol.Optional(CONF_CURRENCY): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_CONVERT_CURRENCY): cv.string,
})

CURRENCY_SCHEMA = vol.Schema({
    vol.Required(CONF_FROM): cv.string,
    vol.Required(CONF_TO): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_FOREIGN_EXCHANGE):
        vol.All(cv.ensure_list, [CURRENCY_SCHEMA]),
    vol.Optional(CONF_SYMBOLS):
        vol.All(cv.ensure_list, [SYMBOL_SCHEMA]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Alpha Vantage sensor."""
    from alpha_vantage.timeseries import TimeSeries
    from alpha_vantage.foreignexchange import ForeignExchange

    api_key = config.get(CONF_API_KEY)
    symbols = config.get(CONF_SYMBOLS, [])
    conversions = config.get(CONF_FOREIGN_EXCHANGE, [])

    if not symbols and not conversions:
        msg = 'Warning: No symbols or currencies configured.'
        hass.components.persistent_notification.create(
            msg, 'Sensor alpha_vantage')
        _LOGGER.warning(msg)
        return

    timeseries = TimeSeries(key=api_key)

    dev = []
    for symbol in symbols:
        try:
            _LOGGER.debug("Configuring timeseries for symbols: %s",
                          symbol[CONF_SYMBOL])
            timeseries.get_intraday(symbol[CONF_SYMBOL])
            sleep(randint(1, 10))  # don't send too much requests per second
        except ValueError:
            _LOGGER.error(
                "API Key is not valid or symbol '%s' not known", symbol)
        dev.append(AlphaVantageSensor(hass, timeseries, symbol))

    forex = ForeignExchange(key=api_key)
    for conversion in conversions:
        from_cur = conversion.get(CONF_FROM)
        to_cur = conversion.get(CONF_TO)
        try:
            _LOGGER.debug("Configuring forex %s - %s", from_cur, to_cur)
            forex.get_currency_exchange_rate(
                from_currency=from_cur, to_currency=to_cur)
            sleep(randint(1, 10))
        except ValueError as error:
            _LOGGER.error(
                "API Key is not valid or currencies '%s'/'%s' not known",
                from_cur, to_cur)
            _LOGGER.debug(str(error))
        dev.append(AlphaVantageForeignExchange(hass, forex, conversion))

    add_entities(dev, True)
    _LOGGER.debug("Setup completed")


class AlphaVantageSensor(Entity):
    """Representation of a Alpha Vantage sensor."""

    def __init__(self, hass, timeseries, symbol):
        """Initialize the sensor."""
        self._hass = hass
        self._symbol = symbol[CONF_SYMBOL]
        self._name = symbol.get(CONF_NAME, self._symbol)
        self._timeseries = timeseries
        self.values = None
        self._unit_of_measurement = symbol.get(CONF_CURRENCY, self._symbol)
        self._icon = ICONS.get(symbol.get(CONF_CURRENCY, 'USD'))
        self._convert_currency = symbol.get(CONF_CONVERT_CURRENCY)
        if self._convert_currency:
            self._last_conversion = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.values['1. open']

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.values is not None:
            return {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_CLOSE: self.values['4. close'],
                ATTR_HIGH: self.values['2. high'],
                ATTR_LOW: self.values['3. low'],
            }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Requesting new data for symbol %s", self._symbol)
        all_values, _ = self._timeseries.get_intraday(self._symbol)
        self.values = next(iter(all_values.values()))
        if self._convert_currency:
            _LOGGER.debug("Converting new values for symbol %s using %s",
                          self._symbol, self._convert_currency)
            converter_state = self._hass.states.get(
                "sensor."+self._convert_currency.lower())
            if not converter_state or converter_state.state == STATE_UNKNOWN:
                _LOGGER.warning("currency converter %s not found",
                                "sensor."+self._convert_currency.lower())
                if not self._last_conversion:
                    self.values = None
            else:
                self._last_conversion = float(converter_state.state)
            if self._last_conversion:
                for attribute in ['1. open', '2. high', '3. low', '4. close',
                                  '5. volume']:
                    self.values[attribute] = str(float(
                        self.values[attribute]) * self._last_conversion)


class AlphaVantageForeignExchange(Entity):
    """Sensor for foreign exchange rates."""

    def __init__(self, hass, foreign_exchange, config):
        """Initialize the sensor."""
        self._hass = hass
        self._foreign_exchange = foreign_exchange
        self._from_currency = config.get(CONF_FROM)
        self._to_currency = config.get(CONF_TO)
        if CONF_NAME in config:
            self._name = config.get(CONF_NAME)
        else:
            self._name = '{}/{}'.format(self._to_currency, self._from_currency)
        self._unit_of_measurement = self._to_currency
        self._icon = ICONS.get(self._from_currency, 'USD')
        self.values = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(float(self.values['5. Exchange Rate']), 4)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.values is not None:
            return {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                CONF_FROM: self._from_currency,
                CONF_TO: self._to_currency,
            }

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Requesting new data for forex %s - %s",
                      self._from_currency, self._to_currency)
        self.values, _ = self._foreign_exchange.get_currency_exchange_rate(
            from_currency=self._from_currency, to_currency=self._to_currency)
        _LOGGER.debug("Received new data for forex %s - %s",
                      self._from_currency, self._to_currency)
