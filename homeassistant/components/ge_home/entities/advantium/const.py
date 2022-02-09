from homeassistant.components.water_heater import (
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE
)

SUPPORT_NONE = 0
GE_ADVANTIUM_WITH_TEMPERATURE = (SUPPORT_OPERATION_MODE | SUPPORT_TARGET_TEMPERATURE)
GE_ADVANTIUM = SUPPORT_OPERATION_MODE
