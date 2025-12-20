"""Data models for SolarMax integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import SolarMaxCoordinator


@dataclass
class ArrayConfig:
    """Configuration for a solar array."""

    name: str
    panel_wattage: int
    panel_count: int
    azimuth: int
    tilt: int
    temperature_coefficient: float = -0.4  # %/°C

    @property
    def total_capacity(self) -> int:
        """Return the total capacity of the array in watts."""
        return self.panel_wattage * self.panel_count


@dataclass
class SolarMaxRuntimeData:
    """Runtime data for SolarMax integration."""

    coordinator: SolarMaxCoordinator
    arrays: list[ArrayConfig]


type SolarMaxConfigEntry = ConfigEntry[SolarMaxRuntimeData]
