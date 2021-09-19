"""Support gathering ted5000 information."""
from contextlib import suppress
from datetime import timedelta
import logging

import requests
import voluptuous as vol
import xmltodict

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_HIDDEN,
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CURRENCY_DOLLAR,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TIME_DAYS,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "ted"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODE, default="base"): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ted5000 sensor."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    mode = config.get(CONF_MODE)
    interval = config.get(CONF_SCAN_INTERVAL, MIN_TIME_BETWEEN_UPDATES)
    url = f"http://{host}:{port}/api/LiveData.xml"
    
    lvl = {"base": 1, "advanced": 2, "extended": 3}

    gateway = Ted5000Gateway(url, interval)

    # Get MTU information to create the sensors.
    gateway.update()

    dev = []
    
    # Create MTU sensors
    for mtu in gateway.data:
        dev.append(Ted5000Sensor(gateway, name, mtu, 0, POWER_WATT))
        dev.append(Ted5000Sensor(gateway, name, mtu, 1, ELECTRIC_POTENTIAL_VOLT))
        if lvl[mode] >= 2: # advanced or extended
            dev.append(Ted5000Sensor(gateway, name, mtu, 2, ENERGY_WATT_HOUR))
            dev.append(Ted5000Sensor(gateway, name, mtu, 3, ENERGY_WATT_HOUR))
            dev.append(Ted5000Sensor(gateway, name, mtu, 4, PERCENTAGE))
    
    # Create utility sensors
    if lvl[mode] >= 3: # extended only
        dev.append(Ted5000Utility(gateway, name, 0, ATTR_HIDDEN))       # MTUs Quantity
        dev.append(Ted5000Utility(gateway, name, 1, CURRENCY_DOLLAR))   # Current Rate $/kWh
        dev.append(Ted5000Utility(gateway, name, 2, TIME_DAYS))         # Days left in billing cycle
        dev.append(Ted5000Utility(gateway, name, 3, ATTR_HIDDEN))       # Plan type (Flat, Tier, TOU, Tier+TOU)
        dev.append(Ted5000Utility(gateway, name, 4, ATTR_HIDDEN))       # Current Tier (0 = Disabled)
        dev.append(Ted5000Utility(gateway, name, 5, ATTR_HIDDEN))       # Current TOU (0 = Disabled)
        dev.append(Ted5000Utility(gateway, name, 6, ATTR_HIDDEN))       # Current TOU Description (if Current TOU is 0 => Not Configured)
        dev.append(Ted5000Utility(gateway, name, 7, ATTR_HIDDEN))       # Carbon Rate lbs/kW
        dev.append(Ted5000Utility(gateway, name, 8, ATTR_HIDDEN))       # Meter read date
        
    add_entities(dev)
    return True


class Ted5000Sensor(SensorEntity):
    """Implementation of a Ted5000 sensor."""

    def __init__(self, gateway, name, mtu, id, unit):
        """Initialize the sensor."""
        dclass = {POWER_WATT: DEVICE_CLASS_POWER, ELECTRIC_POTENTIAL_VOLT: DEVICE_CLASS_VOLTAGE, ENERGY_WATT_HOUR: DEVICE_CLASS_ENERGY, PERCENTAGE: DEVICE_CLASS_POWER_FACTOR}
        sclass = {POWER_WATT: STATE_CLASS_MEASUREMENT, ELECTRIC_POTENTIAL_VOLT: STATE_CLASS_MEASUREMENT, ENERGY_WATT_HOUR: STATE_CLASS_TOTAL_INCREASING, PERCENTAGE: STATE_CLASS_MEASUREMENT}
        suffix = {0: "power", 1: "voltage", 2: "energy_daily", 3: "energy_monthly", 4: "pf"}
        self._gateway = gateway
        self._name = f"{name} mtu{mtu} {suffix[id]}"
        self._mtu = mtu
        self._id = id
        self._unit = unit
        self._dclass = dclass[unit]
        self._sclass = sclass[unit]
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def device_class(self):
        """Return the device class the value is expressed in."""
        return self._dclass
            
    @property
    def state_class(self):
        """Return the state class the value is expressed in."""
        return self._sclass

    @property
    def native_value(self):
        """Return the state of the resources."""
        with suppress(KeyError):
            return self._gateway.data[self._mtu][self._id]

    def update(self):
        """Get the latest data from REST API."""
        self._gateway.update()


class Ted5000Utility(SensorEntity):
    """Implementation of a Ted5000 utility sensors."""
    
    def __init__(self, gateway, name, id, unit):
        """Initialize the sensor."""
        dclass = {ATTR_HIDDEN: ATTR_HIDDEN, CURRENCY_DOLLAR: DEVICE_CLASS_MONETARY, TIME_DAYS: ATTR_HIDDEN}
        sclass = {ATTR_HIDDEN: ATTR_HIDDEN, CURRENCY_DOLLAR: STATE_CLASS_MEASUREMENT, TIME_DAYS: ATTR_HIDDEN}
        units = {0: ATTR_HIDDEN, 1: "$/kWh", 2: TIME_DAYS, 3: ATTR_HIDDEN, 4: ATTR_HIDDEN, 5: ATTR_HIDDEN, 6: ATTR_HIDDEN, 7: "lbs/kW", 8: ATTR_HIDDEN}
        suffix = {0: "MTUs", 1: "CurrentRate", 2: "DaysLeftInBillingCycle", 3: "PlanType", 4: "CurrentTier", 5: "CurrentTOU", 6: "CurrentTOUDescription", 7: "CarbonRate", 8: "MeterReadDate"}
        self._gateway = gateway
        self._name = f"{name} Utility {suffix[id]}"
        self._id = id
        self._unit = units[id]
        self._dclass = dclass[unit]
        self._sclass = sclass[unit]
        self.update()
        
    @property
    def name(self):
        """Return the friendly_name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._unit is not ATTR_HIDDEN:
            return self._unit

    @property
    def device_class(self):
        """Return the device class the value is expressed in."""
        if self._dclass is not ATTR_HIDDEN:
            return self._dclass
            
    @property
    def state_class(self):
        """Return the state class the value is expressed in."""
        if self._sclass is not ATTR_HIDDEN:
            return self._sclass

    @property
    def native_value(self):
        """Return the state of the resources."""
        with suppress(KeyError):
            return self._gateway.dataUtility[self._id]

    def update(self):
        """Get the latest data from REST API."""
        self._gateway.update()
        

class Ted5000Gateway:
    """The class for handling the data retrieval."""

    def __init__(self, url, interval):
        """Initialize the data object."""
        self.url = url
        MIN_TIME_BETWEEN_UPDATES = interval
        self.data = {}
        self.dataUtility = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Ted5000 XML API."""

        try:
            request = requests.get(self.url, timeout=10)
        except requests.exceptions.RequestException as err:
            _LOGGER.error("No connection to endpoint: %s", err)
        else:
            doc = xmltodict.parse(request.text)
            mtus = int(doc["LiveData"]["System"]["NumberMTU"])

            """MTU data"""
            for mtu in range(1, mtus + 1):
                power = int(doc["LiveData"]["Power"]["MTU%d" % mtu]["PowerNow"])
                voltage = int(doc["LiveData"]["Voltage"]["MTU%d" % mtu]["VoltageNow"])
                pf = int(doc["LiveData"]["Power"]["MTU%d" % mtu]["PF"])
                energy_daily = int(doc["LiveData"]["Power"]["MTU%d" % mtu]["PowerTDY"])
                energy_monthly = int(doc["LiveData"]["Power"]["MTU%d" % mtu]["PowerMTD"])

                self.data[mtu] = {
                    0: power,
                    1: voltage / 10,
                    2: energy_daily,
                    3: energy_monthly,
                    4: pf / 10,
                }

            """Utility Data"""
            CurrentRate = int(doc["LiveData"]["Utility"]["CurrentRate"])
            DaysLeftInBillingCycle = int(doc["LiveData"]["Utility"]["DaysLeftInBillingCycle"])
            PlanType = int(doc["LiveData"]["Utility"]["PlanType"])
            PlanTypeString = {0: "Flat", 1: "Tier", 2: "TOU", 3: "Tier+TOU"}
            CarbonRate = int(doc["LiveData"]["Utility"]["CarbonRate"])
            MeterReadDate = int(doc["LiveData"]["Utility"]["MeterReadDate"])
            
            if PlanType == 0 or PlanType == 2:
                CurrentTier = 0
            else:
                CurrentTier = int(doc["LiveData"]["Utility"]["CurrentTier"]) + 1
                
            if PlanType < 2:
                CurrentTOU = 0
                CurrentTOUDescription = "Not Configured"
            else:
                CurrentTOU = int(doc["LiveData"]["Utility"]["CurrentTOU"]) + 1
                CurrentTOUDescription = doc["LiveData"]["Utility"]["CurrentTOUDescription"]
            
            self.dataUtility = {
                0: mtus,
                1: CurrentRate / 100000,
                2: DaysLeftInBillingCycle,
                3: PlanTypeString[PlanType],
                4: CurrentTier,
                5: CurrentTOU,
                6: CurrentTOUDescription,
                7: CarbonRate / 100,
                8: MeterReadDate,
            }
