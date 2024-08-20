"""Models for the BSB-Lan integration."""

from dataclasses import dataclass

from bsblan.models import Sensor, State


@dataclass
class BSBLanCoordinatorData:
    """BSBLan data stored in the Home Assistant data object."""

    state: State
    sensor: Sensor
