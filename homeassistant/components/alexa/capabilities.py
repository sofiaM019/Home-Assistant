"""Alexa capabilities."""

from __future__ import annotations

from collections.abc import Generator
import logging
from typing import Any

from homeassistant.components import (
    button,
    climate,
    cover,
    fan,
    humidifier,
    image_processing,
    input_button,
    input_number,
    light,
    media_player,
    number,
    remote,
    timer,
    vacuum,
    valve,
    water_heater,
)
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.components.climate import HVACMode
from homeassistant.const import (
    ATTR_CODE_FORMAT,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_IDLE,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
    UnitOfLength,
    UnitOfMass,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, State
import homeassistant.util.color as color_util
import homeassistant.util.dt as dt_util

from .const import (
    API_TEMP_UNITS,
    API_THERMOSTAT_MODES,
    API_THERMOSTAT_PRESETS,
    DATE_FORMAT,
    PRESET_MODE_NA,
    Inputs,
)
from .errors import UnsupportedProperty
from .resources import (
    AlexaCapabilityResource,
    AlexaGlobalCatalog,
    AlexaModeResource,
    AlexaPresetResource,
    AlexaSemantics,
)

_LOGGER = logging.getLogger(__name__)

UNIT_TO_CATALOG_TAG = {
    UnitOfTemperature.CELSIUS: AlexaGlobalCatalog.UNIT_TEMPERATURE_CELSIUS,
    UnitOfTemperature.FAHRENHEIT: AlexaGlobalCatalog.UNIT_TEMPERATURE_FAHRENHEIT,
    UnitOfTemperature.KELVIN: AlexaGlobalCatalog.UNIT_TEMPERATURE_KELVIN,
    UnitOfLength.METERS: AlexaGlobalCatalog.UNIT_DISTANCE_METERS,
    UnitOfLength.KILOMETERS: AlexaGlobalCatalog.UNIT_DISTANCE_KILOMETERS,
    UnitOfLength.INCHES: AlexaGlobalCatalog.UNIT_DISTANCE_INCHES,
    UnitOfLength.FEET: AlexaGlobalCatalog.UNIT_DISTANCE_FEET,
    UnitOfLength.YARDS: AlexaGlobalCatalog.UNIT_DISTANCE_YARDS,
    UnitOfLength.MILES: AlexaGlobalCatalog.UNIT_DISTANCE_MILES,
    UnitOfMass.GRAMS: AlexaGlobalCatalog.UNIT_MASS_GRAMS,
    UnitOfMass.KILOGRAMS: AlexaGlobalCatalog.UNIT_MASS_KILOGRAMS,
    UnitOfMass.POUNDS: AlexaGlobalCatalog.UNIT_WEIGHT_POUNDS,
    UnitOfMass.OUNCES: AlexaGlobalCatalog.UNIT_WEIGHT_OUNCES,
    UnitOfVolume.LITERS: AlexaGlobalCatalog.UNIT_VOLUME_LITERS,
    UnitOfVolume.CUBIC_FEET: AlexaGlobalCatalog.UNIT_VOLUME_CUBIC_FEET,
    UnitOfVolume.CUBIC_METERS: AlexaGlobalCatalog.UNIT_VOLUME_CUBIC_METERS,
    UnitOfVolume.GALLONS: AlexaGlobalCatalog.UNIT_VOLUME_GALLONS,
    PERCENTAGE: AlexaGlobalCatalog.UNIT_PERCENT,
    "preset": AlexaGlobalCatalog.SETTING_PRESET,
}


def get_resource_by_unit_of_measurement(entity: State) -> str:
    """Translate the unit of measurement to an Alexa Global Catalog keyword."""
    unit: str = entity.attributes.get("unit_of_measurement", "preset")
    return UNIT_TO_CATALOG_TAG.get(unit, AlexaGlobalCatalog.SETTING_PRESET)


class AlexaCapability:
    """Base class for Alexa capability interfaces.

    The Smart Home Skills API defines a number of "capability interfaces",
    roughly analogous to domains in Home Assistant. The supported interfaces
    describe what actions can be performed on a particular device.

    https://developer.amazon.com/docs/device-apis/message-guide.html
    """

    _resource: AlexaCapabilityResource | None
    _semantics: AlexaSemantics | None
    supported_locales: set[str] = {"en-US"}

    def __init__(
        self,
        entity: State,
        instance: str | None = None,
        non_controllable_properties: bool | None = None,
    ) -> None:
        """Initialize an Alexa capability."""
        self.entity = entity
        self.instance = instance
        self._non_controllable_properties = non_controllable_properties

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        raise NotImplementedError

    def properties_supported(self) -> list[dict]:
        """Return what properties this entity supports."""
        return []

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return False

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return False

    def properties_non_controllable(self) -> bool | None:
        """Return True if non controllable."""
        return self._non_controllable_properties

    def get_property(self, name: str) -> dict[str, Any]:
        """Read and return a property.

        Return value should be a dict, or raise UnsupportedProperty.

        Properties can also have a timeOfSample and uncertaintyInMilliseconds,
        but returning those metadata is not yet implemented.
        """
        raise UnsupportedProperty(name)

    def supports_deactivation(self) -> bool | None:
        """Applicable only to scenes."""

    def capability_proactively_reported(self) -> bool | None:
        """Return True if the capability is proactively reported.

        Set properties_proactively_reported() for proactively reported properties.
        Applicable to DoorbellEventSource.
        """

    def capability_resources(self) -> dict[str, list[dict[str, Any]]]:
        """Return the capability object.

        Applicable to ToggleController, RangeController, and ModeController interfaces.
        """
        return {}

    def configuration(self) -> dict[str, Any] | None:
        """Return the configuration object.

        Applicable to the ThermostatController, SecurityControlPanel, ModeController,
        RangeController, and EventDetectionSensor.
        """

    def configurations(self) -> dict[str, Any] | None:
        """Return the configurations object.

        The plural configurations object is different that the singular configuration
        object. Applicable to EqualizerController interface.
        """

    def inputs(self) -> list[dict[str, str]] | None:
        """Applicable only to media players."""

    def semantics(self) -> dict[str, Any] | None:
        """Return the semantics object.

        Applicable to ToggleController, RangeController, and ModeController interfaces.
        """

    def supported_operations(self) -> list[str]:
        """Return the supportedOperations object."""
        return []

    def camera_stream_configurations(self) -> list[dict[str, Any]] | None:
        """Applicable only to CameraStreamController."""

    def serialize_discovery(self) -> dict[str, Any]:
        """Serialize according to the Discovery API."""
        result: dict[str, Any] = {
            "type": "AlexaInterface",
            "interface": self.name(),
            "version": "3",
        }

        if (instance := self.instance) is not None:
            result["instance"] = instance

        if properties_supported := self.properties_supported():
            result["properties"] = {
                "supported": properties_supported,
                "proactivelyReported": self.properties_proactively_reported(),
                "retrievable": self.properties_retrievable(),
            }

        if (proactively_reported := self.capability_proactively_reported()) is not None:
            result["proactivelyReported"] = proactively_reported

        if (non_controllable := self.properties_non_controllable()) is not None:
            result["properties"]["nonControllable"] = non_controllable

        if (supports_deactivation := self.supports_deactivation()) is not None:
            result["supportsDeactivation"] = supports_deactivation

        if capability_resources := self.capability_resources():
            result["capabilityResources"] = capability_resources

        if configuration := self.configuration():
            result["configuration"] = configuration

        # The plural configurations object is different than the singular
        # configuration object above.
        if configurations := self.configurations():
            result["configurations"] = configurations

        if semantics := self.semantics():
            result["semantics"] = semantics

        if supported_operations := self.supported_operations():
            result["supportedOperations"] = supported_operations

        if inputs := self.inputs():
            result["inputs"] = inputs

        if camera_stream_configurations := self.camera_stream_configurations():
            result["cameraStreamConfigurations"] = camera_stream_configurations

        return result

    def serialize_properties(self) -> Generator[dict[str, Any]]:
        """Return properties serialized for an API response."""
        for prop in self.properties_supported():
            prop_name = prop["name"]
            try:
                prop_value = self.get_property(prop_name)
            except UnsupportedProperty:
                raise
            except Exception:
                _LOGGER.exception(
                    "Unexpected error getting %s.%s property from %s",
                    self.name(),
                    prop_name,
                    self.entity,
                )
                prop_value = None

            if prop_value is None:
                continue

            result = {
                "name": prop_name,
                "namespace": self.name(),
                "value": prop_value,
                "timeOfSample": dt_util.utcnow().strftime(DATE_FORMAT),
                "uncertaintyInMilliseconds": 0,
            }
            if (instance := self.instance) is not None:
                result["instance"] = instance

            yield result


class Alexa(AlexaCapability):
    """Implements Alexa Interface.

    Although endpoints implement this interface implicitly,
    The API suggests you should explicitly include this interface.

    https://developer.amazon.com/docs/device-apis/alexa-interface.html

    To compare current supported locales in Home Assistant
    with Alexa supported locales, run the following script:
    python -m script.alexa_locales
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa"


class AlexaEndpointHealth(AlexaCapability):
    """Implements Alexa.EndpointHealth.

    https://developer.amazon.com/docs/smarthome/state-reporting-for-a-smart-home-skill.html#report-state-when-alexa-requests-it
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(self, hass: HomeAssistant, entity: State) -> None:
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.EndpointHealth"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "connectivity"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "connectivity":
            raise UnsupportedProperty(name)

        if self.entity.state == STATE_UNAVAILABLE:
            return {"value": "UNREACHABLE"}
        return {"value": "OK"}


class AlexaPowerController(AlexaCapability):
    """Implements Alexa.PowerController.

    https://developer.amazon.com/docs/device-apis/alexa-powercontroller.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.PowerController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "powerState"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "powerState":
            raise UnsupportedProperty(name)

        if self.entity.domain == climate.DOMAIN:
            is_on = self.entity.state != climate.HVACMode.OFF
        elif self.entity.domain == fan.DOMAIN:
            is_on = self.entity.state == fan.STATE_ON
        elif self.entity.domain == humidifier.DOMAIN:
            is_on = self.entity.state == humidifier.STATE_ON
        elif self.entity.domain == remote.DOMAIN:
            is_on = self.entity.state not in (STATE_OFF, STATE_UNKNOWN)
        elif self.entity.domain == vacuum.DOMAIN:
            is_on = self.entity.state == vacuum.STATE_CLEANING
        elif self.entity.domain == timer.DOMAIN:
            is_on = self.entity.state != STATE_IDLE
        elif self.entity.domain == water_heater.DOMAIN:
            is_on = self.entity.state not in (STATE_OFF, STATE_UNKNOWN)
        else:
            is_on = self.entity.state != STATE_OFF

        return "ON" if is_on else "OFF"


class AlexaLockController(AlexaCapability):
    """Implements Alexa.LockController.

    https://developer.amazon.com/docs/device-apis/alexa-lockcontroller.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.LockController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "lockState"}]

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "lockState":
            raise UnsupportedProperty(name)

        # If its unlocking its still locked and not unlocked yet
        if self.entity.state in (STATE_UNLOCKING, STATE_LOCKED):
            return "LOCKED"
        # If its locking its still unlocked and not locked yet
        if self.entity.state in (STATE_LOCKING, STATE_UNLOCKED):
            return "UNLOCKED"
        return "JAMMED"


class AlexaSceneController(AlexaCapability):
    """Implements Alexa.SceneController.

    https://developer.amazon.com/docs/device-apis/alexa-scenecontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(self, entity: State, supports_deactivation: bool) -> None:
        """Initialize the entity."""
        self._supports_deactivation = supports_deactivation
        super().__init__(entity)

    def supports_deactivation(self) -> bool | None:
        """Return True if the Scene controller supports deactivation."""
        return self._supports_deactivation

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.SceneController"


class AlexaBrightnessController(AlexaCapability):
    """Implements Alexa.BrightnessController.

    https://developer.amazon.com/docs/device-apis/alexa-brightnesscontroller.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.BrightnessController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "brightness"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "brightness":
            raise UnsupportedProperty(name)
        if brightness := self.entity.attributes.get("brightness"):
            return round(brightness / 255.0 * 100)
        return 0


class AlexaColorController(AlexaCapability):
    """Implements Alexa.ColorController.

    https://developer.amazon.com/docs/device-apis/alexa-colorcontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.ColorController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "color"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "color":
            raise UnsupportedProperty(name)

        hue_saturation: tuple[float, float] | None
        if (hue_saturation := self.entity.attributes.get(light.ATTR_HS_COLOR)) is None:
            hue_saturation = (0, 0)
        if (brightness := self.entity.attributes.get(light.ATTR_BRIGHTNESS)) is None:
            brightness = 0

        return {
            "hue": hue_saturation[0],
            "saturation": hue_saturation[1] / 100.0,
            "brightness": brightness / 255.0,
        }


class AlexaColorTemperatureController(AlexaCapability):
    """Implements Alexa.ColorTemperatureController.

    https://developer.amazon.com/docs/device-apis/alexa-colortemperaturecontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.ColorTemperatureController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "colorTemperatureInKelvin"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "colorTemperatureInKelvin":
            raise UnsupportedProperty(name)
        if color_temp := self.entity.attributes.get("color_temp"):
            return color_util.color_temperature_mired_to_kelvin(color_temp)
        return None


class AlexaSpeaker(AlexaCapability):
    """Implements Alexa.Speaker.

    https://developer.amazon.com/docs/device-apis/alexa-speaker.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "fr-FR",  # Not documented as of 2021-12-04, see PR #60489
        "it-IT",
        "ja-JP",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.Speaker"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        properties = [{"name": "volume"}]

        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & media_player.MediaPlayerEntityFeature.VOLUME_MUTE:
            properties.append({"name": "muted"})

        return properties

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name == "volume":
            current_level = self.entity.attributes.get(
                media_player.ATTR_MEDIA_VOLUME_LEVEL
            )
            if current_level is not None:
                return round(float(current_level) * 100)

        if name == "muted":
            return bool(
                self.entity.attributes.get(media_player.ATTR_MEDIA_VOLUME_MUTED)
            )

        return None


class AlexaStepSpeaker(AlexaCapability):
    """Implements Alexa.StepSpeaker.

    https://developer.amazon.com/docs/device-apis/alexa-stepspeaker.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",  # Not documented as of 2021-12-04, see PR #60489
        "it-IT",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.StepSpeaker"


class AlexaPlaybackController(AlexaCapability):
    """Implements Alexa.PlaybackController.

    https://developer.amazon.com/docs/device-apis/alexa-playbackcontroller.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.PlaybackController"

    def supported_operations(self) -> list[str]:
        """Return the supportedOperations object.

        Supported Operations: FastForward, Next, Pause, Play, Previous, Rewind,
        StartOver, Stop
        """
        supported_features = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        operations = {
            media_player.MediaPlayerEntityFeature.NEXT_TRACK: "Next",
            media_player.MediaPlayerEntityFeature.PAUSE: "Pause",
            media_player.MediaPlayerEntityFeature.PLAY: "Play",
            media_player.MediaPlayerEntityFeature.PREVIOUS_TRACK: "Previous",
            media_player.MediaPlayerEntityFeature.STOP: "Stop",
        }

        return [
            value
            for operation, value in operations.items()
            if operation & supported_features
        ]


class AlexaInputController(AlexaCapability):
    """Implements Alexa.InputController.

    https://developer.amazon.com/docs/device-apis/alexa-inputcontroller.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.InputController"

    def inputs(self) -> list[dict[str, str]] | None:
        """Return the list of valid supported inputs."""
        source_list: list[Any] = (
            self.entity.attributes.get(media_player.ATTR_INPUT_SOURCE_LIST) or []
        )
        return AlexaInputController.get_valid_inputs(source_list)

    @staticmethod
    def get_valid_inputs(source_list: list[Any]) -> list[dict[str, str]]:
        """Return list of supported inputs."""
        input_list: list[dict[str, str]] = []
        for source in source_list:
            if not isinstance(source, str):
                continue
            formatted_source = (
                source.lower().replace("-", "").replace("_", "").replace(" ", "")
            )
            if formatted_source in Inputs.VALID_SOURCE_NAME_MAP:
                input_list.append(
                    {"name": Inputs.VALID_SOURCE_NAME_MAP[formatted_source]}
                )

        return input_list


class AlexaTemperatureSensor(AlexaCapability):
    """Implements Alexa.TemperatureSensor.

    https://developer.amazon.com/docs/device-apis/alexa-temperaturesensor.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(self, hass: HomeAssistant, entity: State) -> None:
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.TemperatureSensor"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "temperature"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "temperature":
            raise UnsupportedProperty(name)

        unit: str = self.entity.attributes.get(
            ATTR_UNIT_OF_MEASUREMENT, self.hass.config.units.temperature_unit
        )
        temp: str | None = self.entity.state
        if self.entity.domain == climate.DOMAIN:
            unit = self.hass.config.units.temperature_unit
            temp = self.entity.attributes.get(climate.ATTR_CURRENT_TEMPERATURE)
        elif self.entity.domain == water_heater.DOMAIN:
            unit = self.hass.config.units.temperature_unit
            temp = self.entity.attributes.get(water_heater.ATTR_CURRENT_TEMPERATURE)

        if temp is None or temp in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None

        try:
            temp_float = float(temp)
        except ValueError:
            _LOGGER.warning("Invalid temp value %s for %s", temp, self.entity.entity_id)
            return None

        # Alexa displays temperatures with one decimal digit, we don't need to do
        # rounding for presentation here.
        return {"value": temp_float, "scale": API_TEMP_UNITS[UnitOfTemperature(unit)]}


class AlexaContactSensor(AlexaCapability):
    """Implements Alexa.ContactSensor.

    The Alexa.ContactSensor interface describes the properties and events used
    to report the state of an endpoint that detects contact between two
    surfaces. For example, a contact sensor can report whether a door or window
    is open.

    https://developer.amazon.com/docs/device-apis/alexa-contactsensor.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(self, hass: HomeAssistant, entity: State) -> None:
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.ContactSensor"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "detectionState"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "detectionState":
            raise UnsupportedProperty(name)

        if self.entity.state == STATE_ON:
            return "DETECTED"
        return "NOT_DETECTED"


class AlexaMotionSensor(AlexaCapability):
    """Implements Alexa.MotionSensor.

    https://developer.amazon.com/docs/device-apis/alexa-motionsensor.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(self, hass: HomeAssistant, entity: State) -> None:
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.MotionSensor"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "detectionState"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "detectionState":
            raise UnsupportedProperty(name)

        if self.entity.state == STATE_ON:
            return "DETECTED"
        return "NOT_DETECTED"


class AlexaThermostatController(AlexaCapability):
    """Implements Alexa.ThermostatController.

    https://developer.amazon.com/docs/device-apis/alexa-thermostatcontroller.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(self, hass: HomeAssistant, entity: State) -> None:
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.ThermostatController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        properties = [{"name": "thermostatMode"}]
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if self.entity.domain == climate.DOMAIN:
            if supported & climate.ClimateEntityFeature.TARGET_TEMPERATURE_RANGE:
                properties.append({"name": "lowerSetpoint"})
                properties.append({"name": "upperSetpoint"})
            if supported & climate.ClimateEntityFeature.TARGET_TEMPERATURE:
                properties.append({"name": "targetSetpoint"})
        elif (
            self.entity.domain == water_heater.DOMAIN
            and supported & water_heater.WaterHeaterEntityFeature.TARGET_TEMPERATURE
        ):
            properties.append({"name": "targetSetpoint"})
        return properties

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if self.entity.state == STATE_UNAVAILABLE:
            return None

        if name == "thermostatMode":
            if self.entity.domain == water_heater.DOMAIN:
                return None
            preset = self.entity.attributes.get(climate.ATTR_PRESET_MODE)

            if preset in API_THERMOSTAT_PRESETS:
                return API_THERMOSTAT_PRESETS[preset]
            if self.entity.state == STATE_UNKNOWN:
                return None
            if self.entity.state not in API_THERMOSTAT_MODES:
                _LOGGER.error(
                    "%s (%s) has unsupported state value '%s'",
                    self.entity.entity_id,
                    type(self.entity),
                    self.entity.state,
                )
                raise UnsupportedProperty(name)
            return API_THERMOSTAT_MODES[HVACMode(self.entity.state)]

        unit = self.hass.config.units.temperature_unit
        temp_attr_map = {
            "targetSetpoint": ATTR_TEMPERATURE,
            "lowerSetpoint": climate.ATTR_TARGET_TEMP_LOW,
            "upperSetpoint": climate.ATTR_TARGET_TEMP_HIGH,
        }

        temp_attr = temp_attr_map.get(name)
        if temp_attr is None:
            raise UnsupportedProperty(name)

        temp = self.entity.attributes.get(temp_attr)
        if temp is None:
            return None

        try:
            temp = float(temp)
        except ValueError:
            _LOGGER.warning(
                "Invalid temp value %s for %s in %s", temp, name, self.entity.entity_id
            )
            return None

        return {"value": temp, "scale": API_TEMP_UNITS[unit]}

    def configuration(self) -> dict[str, Any] | None:
        """Return configuration object.

        Translates climate HVAC_MODES and PRESETS to supported Alexa
        ThermostatMode Values.

        ThermostatMode Value must be AUTO, COOL, HEAT, ECO, OFF, or CUSTOM.
        Water heater devices do not return thermostat modes.
        """
        if self.entity.domain == water_heater.DOMAIN:
            return None

        hvac_modes = self.entity.attributes.get(climate.ATTR_HVAC_MODES) or []
        supported_modes: list[str] = [
            API_THERMOSTAT_MODES[mode]
            for mode in hvac_modes
            if mode in API_THERMOSTAT_MODES
        ]

        preset_modes = self.entity.attributes.get(climate.ATTR_PRESET_MODES)
        if preset_modes:
            for mode in preset_modes:
                thermostat_mode = API_THERMOSTAT_PRESETS.get(mode)
                if thermostat_mode:
                    supported_modes.append(thermostat_mode)

        # Return False for supportsScheduling until supported with event
        # listener in handler.
        configuration: dict[str, Any] = {"supportsScheduling": False}

        if supported_modes:
            configuration["supportedModes"] = supported_modes

        return configuration


class AlexaPowerLevelController(AlexaCapability):
    """Implements Alexa.PowerLevelController.

    https://developer.amazon.com/docs/device-apis/alexa-powerlevelcontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "fr-CA",
        "fr-FR",
        "it-IT",
        "ja-JP",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.PowerLevelController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "powerLevel"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "powerLevel":
            raise UnsupportedProperty(name)


class AlexaSecurityPanelController(AlexaCapability):
    """Implements Alexa.SecurityPanelController.

    https://developer.amazon.com/docs/device-apis/alexa-securitypanelcontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(self, hass: HomeAssistant, entity: State) -> None:
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.SecurityPanelController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "armState"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "armState":
            raise UnsupportedProperty(name)

        arm_state = self.entity.state
        if arm_state == STATE_ALARM_ARMED_HOME:
            return "ARMED_STAY"
        if arm_state == STATE_ALARM_ARMED_AWAY:
            return "ARMED_AWAY"
        if arm_state == STATE_ALARM_ARMED_NIGHT:
            return "ARMED_NIGHT"
        if arm_state == STATE_ALARM_ARMED_CUSTOM_BYPASS:
            return "ARMED_STAY"
        return "DISARMED"

    def configuration(self) -> dict[str, Any] | None:
        """Return configuration object with supported authorization types."""
        code_format = self.entity.attributes.get(ATTR_CODE_FORMAT)
        supported = self.entity.attributes[ATTR_SUPPORTED_FEATURES]
        configuration = {}

        supported_arm_states = [{"value": "DISARMED"}]
        if supported & AlarmControlPanelEntityFeature.ARM_AWAY:
            supported_arm_states.append({"value": "ARMED_AWAY"})
        if supported & AlarmControlPanelEntityFeature.ARM_HOME:
            supported_arm_states.append({"value": "ARMED_STAY"})
        if supported & AlarmControlPanelEntityFeature.ARM_NIGHT:
            supported_arm_states.append({"value": "ARMED_NIGHT"})

        configuration["supportedArmStates"] = supported_arm_states

        if code_format == CodeFormat.NUMBER:
            configuration["supportedAuthorizationTypes"] = [{"type": "FOUR_DIGIT_PIN"}]

        return configuration


class AlexaModeController(AlexaCapability):
    """Implements Alexa.ModeController.

    The instance property must be unique across ModeController, RangeController,
    ToggleController within the same device.

    The instance property should be a concatenated string of device domain period
    and single word. e.g. fan.speed & fan.direction.

    The instance property must not contain words from other instance property
    strings within the same device. e.g. Instance property cover.position &
    cover.tilt_position will cause the Alexa.Discovery directive to fail.

    An instance property string value may be reused for different devices.

    https://developer.amazon.com/docs/device-apis/alexa-modecontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(
        self, entity: State, instance: str, non_controllable: bool = False
    ) -> None:
        """Initialize the entity."""
        AlexaCapability.__init__(self, entity, instance, non_controllable)
        self._resource = None
        self._semantics = None

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.ModeController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "mode"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "mode":
            raise UnsupportedProperty(name)

        instance_map = {
            f"{fan.DOMAIN}.{fan.ATTR_DIRECTION}": {
                "attr": fan.ATTR_DIRECTION,
                "valid_modes": (fan.DIRECTION_FORWARD, fan.DIRECTION_REVERSE, STATE_UNKNOWN),
                "prefix": fan.ATTR_DIRECTION,
            },
            f"{fan.DOMAIN}.{fan.ATTR_PRESET_MODE}": {
                "attr": fan.ATTR_PRESET_MODE,
                "valid_modes": self.entity.attributes.get(fan.ATTR_PRESET_MODES, None),
                "prefix": fan.ATTR_PRESET_MODE,
            },
            f"{humidifier.DOMAIN}.{humidifier.ATTR_MODE}": {
                "attr": humidifier.ATTR_MODE,
                "valid_modes": self.entity.attributes.get(humidifier.ATTR_AVAILABLE_MODES, []),
                "prefix": humidifier.ATTR_MODE,
            },
            f"{remote.DOMAIN}.{remote.ATTR_ACTIVITY}": {
                "attr": remote.ATTR_CURRENT_ACTIVITY,
                "valid_modes": self.entity.attributes.get(remote.ATTR_ACTIVITY_LIST, []),
                "prefix": remote.ATTR_ACTIVITY,
            },
            f"{water_heater.DOMAIN}.{water_heater.ATTR_OPERATION_MODE}": {
                "attr": water_heater.ATTR_OPERATION_MODE,
                "valid_modes": self.entity.attributes.get(water_heater.ATTR_OPERATION_LIST, []),
                "prefix": water_heater.ATTR_OPERATION_MODE,
            },
            f"{cover.DOMAIN}.{cover.ATTR_POSITION}": {
                "attr": None, # Return state instead of position when using ModeController.
                "valid_modes": (
                    cover.STATE_OPEN,
                    cover.STATE_OPENING,
                    cover.STATE_CLOSED,
                    cover.STATE_CLOSING,
                    STATE_UNKNOWN,
                ),
                "prefix": cover.ATTR_POSITION,
            },
            f"{valve.DOMAIN}.state": {
                "attr": None, # Return state instead of position when using ModeController.
                "valid_modes": (
                    valve.STATE_OPEN,
                    valve.STATE_OPENING,
                    valve.STATE_CLOSED,
                    valve.STATE_CLOSING,
                    STATE_UNKNOWN,
                ),
                "prefix": "state",
            },
        }

        if self.instance in instance_map:
            instance_info = instance_map[self.instance]
            mode = (
                self.entity.attributes.get(instance_info["attr"]) if instance_info["attr"] else self.entity.state
            )

            if mode in instance_info["valid_modes"]:
                return f"{instance_info['prefix']}.{mode}"

        return None

    def configuration(self) -> dict[str, Any] | None:
        """Return configuration with modeResources."""
        if isinstance(self._resource, AlexaCapabilityResource):
            return self._resource.serialize_configuration()

        return None

    def capability_resources(self) -> dict[str, list[dict[str, Any]]]:
        """Return capabilityResources object."""

        def create_resource(catalog_setting, mode_list, prefix, na_mode=PRESET_MODE_NA):
            resource = AlexaModeResource([catalog_setting], False)
            for mode in mode_list:
                resource.add_mode(f"{prefix}.{mode}", [mode])
            if len(mode_list) == 1:
                resource.add_mode(f"{prefix}.{na_mode}", [na_mode])
            return resource.serialize_capability_resources()

        instance_map = {
            f"{fan.DOMAIN}.{fan.ATTR_DIRECTION}": {
                "catalog_setting": AlexaGlobalCatalog.SETTING_DIRECTION,
                "mode_list": [fan.DIRECTION_FORWARD, fan.DIRECTION_REVERSE],
                "prefix": fan.ATTR_DIRECTION,
            },
            f"{fan.DOMAIN}.{fan.ATTR_PRESET_MODE}": {
                "catalog_setting": AlexaGlobalCatalog.SETTING_PRESET,
                "mode_list": self.entity.attributes.get(fan.ATTR_PRESET_MODES, []),
                "prefix": fan.ATTR_PRESET_MODE,
            },
            f"{humidifier.DOMAIN}.{humidifier.ATTR_MODE}": {
                "catalog_setting": AlexaGlobalCatalog.SETTING_MODE,
                "mode_list": self.entity.attributes.get(humidifier.ATTR_AVAILABLE_MODES, []),
                "prefix": humidifier.ATTR_MODE,
            },
            f"{water_heater.DOMAIN}.{water_heater.ATTR_OPERATION_MODE}": {
                "catalog_setting": AlexaGlobalCatalog.SETTING_MODE,
                "mode_list": self.entity.attributes.get(water_heater.ATTR_OPERATION_LIST, []),
                "prefix": water_heater.ATTR_OPERATION_MODE,
            },
            f"{remote.DOMAIN}.{remote.ATTR_ACTIVITY}": {
                "catalog_setting": AlexaGlobalCatalog.SETTING_MODE,
                "mode_list": self.entity.attributes.get(remote.ATTR_ACTIVITY_LIST, []),
                "prefix": remote.ATTR_ACTIVITY,
            },
            f"{cover.DOMAIN}.{cover.ATTR_POSITION}": {
                "catalog_setting": AlexaGlobalCatalog.SETTING_OPENING,
                "mode_list": [cover.STATE_OPEN, cover.STATE_CLOSED],
                "prefix": cover.ATTR_POSITION,
            },
            f"{valve.DOMAIN}.state": {
                "catalog_setting": AlexaGlobalCatalog.SETTING_PRESET,
                "prefix": "state",
                "valve_states": True,
            },
        }

        if self.instance in instance_map:
            config = instance_map[self.instance]

            if config.get("valve_states"):
                supported_features = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
                resource = AlexaModeResource(
                    ["Preset", AlexaGlobalCatalog.SETTING_PRESET], False
                )
                modes = 0
                if supported_features & valve.ValveEntityFeature.OPEN:
                    resource.add_mode(
                        f"state.{valve.STATE_OPEN}",
                        ["Open", AlexaGlobalCatalog.SETTING_PRESET],
                    )
                    modes += 1
                if supported_features & valve.ValveEntityFeature.CLOSE:
                    resource.add_mode(
                        f"state.{valve.STATE_CLOSED}",
                        ["Closed", AlexaGlobalCatalog.SETTING_PRESET],
                    )
                    modes += 1

                # Alexa requires at least 2 modes
                if modes == 1:
                    resource.add_mode(f"state.{PRESET_MODE_NA}", [PRESET_MODE_NA])

                return resource.serialize_capability_resources()

            return create_resource(
                config["catalog_setting"],
                config["mode_list"],
                config["prefix"],
            )

        return {}

    def semantics(self) -> dict[str, Any] | None:
        """Build and return semantics object."""
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        # Cover Position
        if self.instance == f"{cover.DOMAIN}.{cover.ATTR_POSITION}":
            lower_labels = [AlexaSemantics.ACTION_LOWER]
            raise_labels = [AlexaSemantics.ACTION_RAISE]
            self._semantics = AlexaSemantics()

            # Add open/close semantics if tilt is not supported.
            if not supported & cover.CoverEntityFeature.SET_TILT_POSITION:
                lower_labels.append(AlexaSemantics.ACTION_CLOSE)
                raise_labels.append(AlexaSemantics.ACTION_OPEN)
                self._semantics.add_states_to_value(
                    [AlexaSemantics.STATES_CLOSED],
                    f"{cover.ATTR_POSITION}.{cover.STATE_CLOSED}",
                )
                self._semantics.add_states_to_value(
                    [AlexaSemantics.STATES_OPEN],
                    f"{cover.ATTR_POSITION}.{cover.STATE_OPEN}",
                )

            self._semantics.add_action_to_directive(
                lower_labels,
                "SetMode",
                {"mode": f"{cover.ATTR_POSITION}.{cover.STATE_CLOSED}"},
            )
            self._semantics.add_action_to_directive(
                raise_labels,
                "SetMode",
                {"mode": f"{cover.ATTR_POSITION}.{cover.STATE_OPEN}"},
            )

            return self._semantics.serialize_semantics()

        # Valve Position
        if self.instance == f"{valve.DOMAIN}.state":
            close_labels = [AlexaSemantics.ACTION_CLOSE]
            open_labels = [AlexaSemantics.ACTION_OPEN]
            self._semantics = AlexaSemantics()

            self._semantics.add_states_to_value(
                [AlexaSemantics.STATES_CLOSED],
                f"state.{valve.STATE_CLOSED}",
            )
            self._semantics.add_states_to_value(
                [AlexaSemantics.STATES_OPEN],
                f"state.{valve.STATE_OPEN}",
            )

            self._semantics.add_action_to_directive(
                close_labels,
                "SetMode",
                {"mode": f"state.{valve.STATE_CLOSED}"},
            )
            self._semantics.add_action_to_directive(
                open_labels,
                "SetMode",
                {"mode": f"state.{valve.STATE_OPEN}"},
            )

            return self._semantics.serialize_semantics()

        return None


class AlexaRangeController(AlexaCapability):
    """Implements Alexa.RangeController.

    The instance property must be unique across ModeController, RangeController,
    ToggleController within the same device.

    The instance property should be a concatenated string of device domain period
    and single word. e.g. fan.speed & fan.direction.

    The instance property must not contain words from other instance property
    strings within the same device. e.g. Instance property cover.position &
    cover.tilt_position will cause the Alexa.Discovery directive to fail.

    An instance property string value may be reused for different devices.

    https://developer.amazon.com/docs/device-apis/alexa-rangecontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(
        self, entity: State, instance: str | None, non_controllable: bool = False
    ) -> None:
        """Initialize the entity."""
        AlexaCapability.__init__(self, entity, instance, non_controllable)
        self._resource = None
        self._semantics = None

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.RangeController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "rangeValue"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "rangeValue":
            raise UnsupportedProperty(name)

        # Return None for unavailable and unknown states.
        # Allows the Alexa.EndpointHealth Interface to handle the unavailable
        # state in a stateReport.
        if self.entity.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None):
            return None

        instance_map = {
            f"{cover.DOMAIN}.{cover.ATTR_POSITION}": cover.ATTR_CURRENT_POSITION,
            f"{cover.DOMAIN}.tilt": cover.ATTR_CURRENT_TILT_POSITION,
            f"{humidifier.DOMAIN}.{humidifier.ATTR_HUMIDITY}": humidifier.ATTR_HUMIDITY,
            f"{input_number.DOMAIN}.{input_number.ATTR_VALUE}": None,  # Uses entity.state
            f"{number.DOMAIN}.{number.ATTR_VALUE}": None,  # Uses entity.state
            f"{valve.DOMAIN}.{valve.ATTR_POSITION}": valve.ATTR_CURRENT_POSITION,
        }

        if self.instance in instance_map:
            attr = instance_map[self.instance]
            if attr:
                return self.entity.attributes.get(attr)
            return float(self.entity.state)

        # Fan speed percentage
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_PERCENTAGE}":
            supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            if supported and fan.FanEntityFeature.SET_SPEED:
                return self.entity.attributes.get(fan.ATTR_PERCENTAGE)
            return 100 if self.entity.state == fan.STATE_ON else 0

        # Vacuum Fan Speed
        if self.instance == f"{vacuum.DOMAIN}.{vacuum.ATTR_FAN_SPEED}":
            speed_list = self.entity.attributes.get(vacuum.ATTR_FAN_SPEED_LIST)
            speed = self.entity.attributes.get(vacuum.ATTR_FAN_SPEED)
            if speed_list and speed:
                return next((i for i, v in enumerate(speed_list) if v == speed), None)

        return None

    def configuration(self) -> dict[str, Any] | None:
        """Return configuration with presetResources."""
        if isinstance(self._resource, AlexaCapabilityResource):
            return self._resource.serialize_configuration()

        return None

    def capability_resources(self) -> dict[str, list[dict[str, Any]]]:
        """Return capabilityResources object."""

        def create_preset_resource(labels, min_value, max_value, precision, unit=None, speed_list=None):
            """Helper to create AlexaPresetResource."""
            resource = AlexaPresetResource(labels, min_value=min_value, max_value=max_value, precision=precision, unit=unit)
            if speed_list:
                for index, speed in enumerate(speed_list):
                    speed_labels = [speed.replace("_", " ")]
                    if index == 1:
                        speed_labels.append(AlexaGlobalCatalog.VALUE_MINIMUM)
                    if index == len(speed_list) - 1:
                        speed_labels.append(AlexaGlobalCatalog.VALUE_MAXIMUM)
                    resource.add_preset(value=index, labels=speed_labels)
            return resource.serialize_capability_resources()

        instance_map = {
            f"{fan.DOMAIN}.{fan.ATTR_PERCENTAGE}": {
                "labels": ["Percentage", AlexaGlobalCatalog.SETTING_FAN_SPEED],
                "min_value": 0,
                "max_value": 100,
                "precision": 1 if self.entity.attributes.get(fan.ATTR_PERCENTAGE_STEP) else 100,
                "unit": AlexaGlobalCatalog.UNIT_PERCENT,
            },
            f"{humidifier.DOMAIN}.{humidifier.ATTR_HUMIDITY}": {
                "labels": ["Humidity", "Percentage", "Target humidity"],
                "min_value": self.entity.attributes.get(humidifier.ATTR_MIN_HUMIDITY, 10),
                "max_value": self.entity.attributes.get(humidifier.ATTR_MAX_HUMIDITY, 90),
                "precision": 1,
                "unit": AlexaGlobalCatalog.UNIT_PERCENT,
            },
            f"{cover.DOMAIN}.{cover.ATTR_POSITION}": {
                "labels": ["Position", AlexaGlobalCatalog.SETTING_OPENING],
                "min_value": 0,
                "max_value": 100,
                "precision": 1,
                "unit": AlexaGlobalCatalog.UNIT_PERCENT,
            },
            f"{cover.DOMAIN}.tilt": {
                "labels": ["Tilt", "Angle", AlexaGlobalCatalog.SETTING_DIRECTION],
                "min_value": 0,
                "max_value": 100,
                "precision": 1,
                "unit": AlexaGlobalCatalog.UNIT_PERCENT,
            },
            f"{valve.DOMAIN}.{valve.ATTR_POSITION}": {
                "labels": ["Opening", AlexaGlobalCatalog.SETTING_OPENING],
                "min_value": 0,
                "max_value": 100,
                "precision": 1,
                "unit": AlexaGlobalCatalog.UNIT_PERCENT,
            },
        }

        if self.instance in instance_map:
            config = instance_map[self.instance]
            return create_preset_resource(config["labels"], config["min_value"], config["max_value"], config["precision"], config.get("unit"))

        # Input Number Value
        if self.instance == f"{input_number.DOMAIN}.{input_number.ATTR_VALUE}":
            min_value = float(self.entity.attributes[input_number.ATTR_MIN])
            max_value = float(self.entity.attributes[input_number.ATTR_MAX])
            precision = float(self.entity.attributes.get(input_number.ATTR_STEP, 1))
            unit = self.entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

            resource = create_preset_resource(
                ["Value", get_resource_by_unit_of_measurement(self.entity)], min_value, max_value, precision, unit
            )
            self._resource = AlexaPresetResource(["Value"], min_value=min_value, max_value=max_value, precision=precision, unit=unit)
            self._resource.add_preset(value=min_value, labels=[AlexaGlobalCatalog.VALUE_MINIMUM])
            self._resource.add_preset(value=max_value, labels=[AlexaGlobalCatalog.VALUE_MAXIMUM])
            return resource

        # Number Value
        if self.instance == f"{number.DOMAIN}.{number.ATTR_VALUE}":
            min_value = float(self.entity.attributes[number.ATTR_MIN])
            max_value = float(self.entity.attributes[number.ATTR_MAX])
            precision = float(self.entity.attributes.get(number.ATTR_STEP, 1))
            unit = self.entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

            resource = create_preset_resource(
                ["Value", get_resource_by_unit_of_measurement(self.entity)], min_value, max_value, precision, unit
            )
            self._resource = AlexaPresetResource(["Value"], min_value=min_value, max_value=max_value, precision=precision, unit=unit)
            self._resource.add_preset(value=min_value, labels=[AlexaGlobalCatalog.VALUE_MINIMUM])
            self._resource.add_preset(value=max_value, labels=[AlexaGlobalCatalog.VALUE_MAXIMUM])
            return resource

        # Vacuum Fan Speed Resources
        if self.instance == f"{vacuum.DOMAIN}.{vacuum.ATTR_FAN_SPEED}":
            speed_list = self.entity.attributes[vacuum.ATTR_FAN_SPEED_LIST]
            max_value = len(speed_list) - 1
            return create_preset_resource(
                [AlexaGlobalCatalog.SETTING_FAN_SPEED], min_value=0, max_value=max_value, precision=1, speed_list=speed_list
            )

        return {}

    def semantics(self) -> dict[str, Any] | None:
        """Build and return semantics object."""
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        # Cover Position
        if self.instance == f"{cover.DOMAIN}.{cover.ATTR_POSITION}":
            lower_labels = [AlexaSemantics.ACTION_LOWER]
            raise_labels = [AlexaSemantics.ACTION_RAISE]
            self._semantics = AlexaSemantics()

            # Add open/close semantics if tilt is not supported.
            if not supported & cover.CoverEntityFeature.SET_TILT_POSITION:
                lower_labels.append(AlexaSemantics.ACTION_CLOSE)
                raise_labels.append(AlexaSemantics.ACTION_OPEN)
                self._semantics.add_states_to_value(
                    [AlexaSemantics.STATES_CLOSED], value=0
                )
                self._semantics.add_states_to_range(
                    [AlexaSemantics.STATES_OPEN], min_value=1, max_value=100
                )

            self._semantics.add_action_to_directive(
                lower_labels, "SetRangeValue", {"rangeValue": 0}
            )
            self._semantics.add_action_to_directive(
                raise_labels, "SetRangeValue", {"rangeValue": 100}
            )
            return self._semantics.serialize_semantics()

        # Cover Tilt
        if self.instance == f"{cover.DOMAIN}.tilt":
            self._semantics = AlexaSemantics()
            self._semantics.add_action_to_directive(
                [AlexaSemantics.ACTION_CLOSE], "SetRangeValue", {"rangeValue": 0}
            )
            self._semantics.add_action_to_directive(
                [AlexaSemantics.ACTION_OPEN], "SetRangeValue", {"rangeValue": 100}
            )
            self._semantics.add_states_to_value([AlexaSemantics.STATES_CLOSED], value=0)
            self._semantics.add_states_to_range(
                [AlexaSemantics.STATES_OPEN], min_value=1, max_value=100
            )
            return self._semantics.serialize_semantics()

        # Fan Speed Percentage
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_PERCENTAGE}":
            lower_labels = [AlexaSemantics.ACTION_LOWER]
            raise_labels = [AlexaSemantics.ACTION_RAISE]
            self._semantics = AlexaSemantics()

            self._semantics.add_action_to_directive(
                lower_labels, "SetRangeValue", {"rangeValue": 0}
            )
            self._semantics.add_action_to_directive(
                raise_labels, "SetRangeValue", {"rangeValue": 100}
            )
            return self._semantics.serialize_semantics()

        # Target Humidity Percentage
        if self.instance == f"{humidifier.DOMAIN}.{humidifier.ATTR_HUMIDITY}":
            lower_labels = [AlexaSemantics.ACTION_LOWER]
            raise_labels = [AlexaSemantics.ACTION_RAISE]
            self._semantics = AlexaSemantics()
            min_value = self.entity.attributes.get(humidifier.ATTR_MIN_HUMIDITY, 10)
            max_value = self.entity.attributes.get(humidifier.ATTR_MAX_HUMIDITY, 90)

            self._semantics.add_action_to_directive(
                lower_labels, "SetRangeValue", {"rangeValue": min_value}
            )
            self._semantics.add_action_to_directive(
                raise_labels, "SetRangeValue", {"rangeValue": max_value}
            )
            return self._semantics.serialize_semantics()

        # Valve Position
        if self.instance == f"{valve.DOMAIN}.{valve.ATTR_POSITION}":
            close_labels = [AlexaSemantics.ACTION_CLOSE]
            open_labels = [AlexaSemantics.ACTION_OPEN]
            self._semantics = AlexaSemantics()

            self._semantics.add_states_to_value([AlexaSemantics.STATES_CLOSED], value=0)
            self._semantics.add_states_to_range(
                [AlexaSemantics.STATES_OPEN], min_value=1, max_value=100
            )

            self._semantics.add_action_to_directive(
                close_labels, "SetRangeValue", {"rangeValue": 0}
            )
            self._semantics.add_action_to_directive(
                open_labels, "SetRangeValue", {"rangeValue": 100}
            )
            return self._semantics.serialize_semantics()

        return None


class AlexaToggleController(AlexaCapability):
    """Implements Alexa.ToggleController.

    The instance property must be unique across ModeController, RangeController,
    ToggleController within the same device.

    The instance property should be a concatenated string of device domain period
    and single word. e.g. fan.speed & fan.direction.

    The instance property must not contain words from other instance property
    strings within the same device. e.g. Instance property cover.position
    & cover.tilt_position will cause the Alexa.Discovery directive to fail.

    An instance property string value may be reused for different devices.

    https://developer.amazon.com/docs/device-apis/alexa-togglecontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(
        self, entity: State, instance: str, non_controllable: bool = False
    ) -> None:
        """Initialize the entity."""
        AlexaCapability.__init__(self, entity, instance, non_controllable)
        self._resource = None
        self._semantics = None

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.ToggleController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "toggleState"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "toggleState":
            raise UnsupportedProperty(name)

        # Fan Oscillating
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_OSCILLATING}":
            is_on = bool(self.entity.attributes.get(fan.ATTR_OSCILLATING))
            return "ON" if is_on else "OFF"

        # Stop Valve
        if self.instance == f"{valve.DOMAIN}.stop":
            return "OFF"

        return None

    def capability_resources(self) -> dict[str, list[dict[str, Any]]]:
        """Return capabilityResources object."""

        # Fan Oscillating Resource
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_OSCILLATING}":
            self._resource = AlexaCapabilityResource(
                [AlexaGlobalCatalog.SETTING_OSCILLATE, "Rotate", "Rotation"]
            )
            return self._resource.serialize_capability_resources()

        if self.instance == f"{valve.DOMAIN}.stop":
            self._resource = AlexaCapabilityResource(["Stop"])
            return self._resource.serialize_capability_resources()

        return {}


class AlexaChannelController(AlexaCapability):
    """Implements Alexa.ChannelController.

    https://developer.amazon.com/docs/device-apis/alexa-channelcontroller.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.ChannelController"


class AlexaDoorbellEventSource(AlexaCapability):
    """Implements Alexa.DoorbellEventSource.

    https://developer.amazon.com/docs/device-apis/alexa-doorbelleventsource.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.DoorbellEventSource"

    def capability_proactively_reported(self) -> bool:
        """Return True for proactively reported capability."""
        return True


class AlexaPlaybackStateReporter(AlexaCapability):
    """Implements Alexa.PlaybackStateReporter.

    https://developer.amazon.com/docs/device-apis/alexa-playbackstatereporter.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.PlaybackStateReporter"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "playbackState"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "playbackState":
            raise UnsupportedProperty(name)

        playback_state = self.entity.state
        if playback_state == STATE_PLAYING:
            return {"state": "PLAYING"}
        if playback_state == STATE_PAUSED:
            return {"state": "PAUSED"}

        return {"state": "STOPPED"}


class AlexaSeekController(AlexaCapability):
    """Implements Alexa.SeekController.

    https://developer.amazon.com/docs/device-apis/alexa-seekcontroller.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.SeekController"


class AlexaEventDetectionSensor(AlexaCapability):
    """Implements Alexa.EventDetectionSensor.

    https://developer.amazon.com/docs/device-apis/alexa-eventdetectionsensor.html
    """

    supported_locales = {"en-US"}

    def __init__(self, hass: HomeAssistant, entity: State) -> None:
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.EventDetectionSensor"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports."""
        return [{"name": "humanPresenceDetectionState"}]

    def properties_proactively_reported(self) -> bool:
        """Return True if properties asynchronously reported."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "humanPresenceDetectionState":
            raise UnsupportedProperty(name)

        human_presence = "NOT_DETECTED"
        state = self.entity.state

        # Return None for unavailable and unknown states.
        # Allows the Alexa.EndpointHealth Interface to handle the unavailable
        # state in a stateReport.
        if state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None):
            return None

        if self.entity.domain == image_processing.DOMAIN:
            if int(state):
                human_presence = "DETECTED"
        elif state == STATE_ON or self.entity.domain in [
            input_button.DOMAIN,
            button.DOMAIN,
        ]:
            human_presence = "DETECTED"

        return {"value": human_presence}

    def configuration(self) -> dict[str, Any] | None:
        """Return supported detection types."""
        return {
            "detectionMethods": ["AUDIO", "VIDEO"],
            "detectionModes": {
                "humanPresence": {
                    "featureAvailability": "ENABLED",
                    "supportsNotDetected": self.entity.domain
                    not in [input_button.DOMAIN, button.DOMAIN],
                }
            },
        }


class AlexaEqualizerController(AlexaCapability):
    """Implements Alexa.EqualizerController.

    https://developer.amazon.com/en-US/docs/alexa/device-apis/alexa-equalizercontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    VALID_SOUND_MODES = {
        "MOVIE",
        "MUSIC",
        "NIGHT",
        "SPORT",
        "TV",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.EqualizerController"

    def properties_supported(self) -> list[dict[str, str]]:
        """Return what properties this entity supports.

        Either bands, mode or both can be specified. Only mode is supported
        at this time.
        """
        return [{"name": "mode"}]

    def properties_retrievable(self) -> bool:
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name: str) -> Any:
        """Read and return a property."""
        if name != "mode":
            raise UnsupportedProperty(name)

        sound_mode = self.entity.attributes.get(media_player.ATTR_SOUND_MODE)
        if sound_mode and sound_mode.upper() in self.VALID_SOUND_MODES:
            return sound_mode.upper()

        return None

    def configurations(self) -> dict[str, Any] | None:
        """Return the sound modes supported in the configurations object."""
        configurations = None
        supported_sound_modes = self.get_valid_inputs(
            self.entity.attributes.get(media_player.ATTR_SOUND_MODE_LIST) or []
        )
        if supported_sound_modes:
            configurations = {"modes": {"supported": supported_sound_modes}}

        return configurations

    @classmethod
    def get_valid_inputs(cls, sound_mode_list: list[str]) -> list[dict[str, str]]:
        """Return list of supported inputs."""
        input_list: list[dict[str, str]] = []
        for sound_mode in sound_mode_list:
            sound_mode = sound_mode.upper()

            if sound_mode in cls.VALID_SOUND_MODES:
                input_list.append({"name": sound_mode})

        return input_list


class AlexaTimeHoldController(AlexaCapability):
    """Implements Alexa.TimeHoldController.

    https://developer.amazon.com/docs/device-apis/alexa-timeholdcontroller.html
    """

    supported_locales = {"en-US"}

    def __init__(self, entity: State, allow_remote_resume: bool = False) -> None:
        """Initialize the entity."""
        super().__init__(entity)
        self._allow_remote_resume = allow_remote_resume

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.TimeHoldController"

    def configuration(self) -> dict[str, Any] | None:
        """Return configuration object.

        Set allowRemoteResume to True if Alexa can restart the operation on the device.
        When false, Alexa does not send the Resume directive.
        """
        return {"allowRemoteResume": self._allow_remote_resume}


class AlexaCameraStreamController(AlexaCapability):
    """Implements Alexa.CameraStreamController.

    https://developer.amazon.com/docs/device-apis/alexa-camerastreamcontroller.html
    """

    supported_locales = {
        "ar-SA",
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        return "Alexa.CameraStreamController"

    def camera_stream_configurations(self) -> list[dict[str, Any]] | None:
        """Return cameraStreamConfigurations object."""
        return [
            {
                "protocols": ["HLS"],
                "resolutions": [{"width": 1280, "height": 720}],
                "authorizationTypes": ["NONE"],
                "videoCodecs": ["H264"],
                "audioCodecs": ["AAC"],
            }
        ]
