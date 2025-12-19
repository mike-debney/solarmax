"""Data update coordinator for SolarMax integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

import pvlib
from pvlib.location import Location
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, STC_IRRADIANCE, UPDATE_INTERVAL
from .models import ArrayConfig

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


class SolarMaxCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Coordinator to manage solar power calculations."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        arrays: list[ArrayConfig],
        solar_radiation_entity: str,
        latitude: float,
        longitude: float,
        inverter_efficiency: float,
        inverter_capacity: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            config_entry=config_entry,
        )
        self.solar_radiation_entity = solar_radiation_entity
        self.arrays = arrays
        self.latitude = latitude
        self.longitude = longitude
        self.inverter_efficiency = (
            inverter_efficiency / 100
        )  # Convert percentage to decimal
        self.inverter_capacity = inverter_capacity
        self._location: Any | None = None

    @property
    def location(self) -> Location:
        """Get or create pvlib Location object."""
        if self._location is None:
            self._location = Location(
                latitude=self.latitude,
                longitude=self.longitude,
                tz=self.hass.config.time_zone,
            )
        return self._location

    async def _async_update_data(self) -> dict[str, float]:
        """Fetch data from solar radiation sensor and calculate power output."""
        # Get solar radiation value
        radiation_state = self.hass.states.get(self.solar_radiation_entity)

        if radiation_state is None or radiation_state.state in (
            "unknown",
            "unavailable",
        ):
            raise UpdateFailed(
                f"Solar radiation sensor {self.solar_radiation_entity} is unavailable"
            )

        try:
            solar_radiation = float(radiation_state.state)
        except (ValueError, TypeError) as err:
            raise UpdateFailed(
                f"Invalid solar radiation value: {radiation_state.state}"
            ) from err

        # Calculate power output for each array
        results: dict[str, float] = {}
        total_power = 0.0
        for array in self.arrays:
            power = await self.hass.async_add_executor_job(
                self._calculate_array_power, array, solar_radiation
            )
            results[array.name] = power
            total_power += power

        # Apply inverter capacity clipping to total power
        total_power = min(total_power, self.inverter_capacity)
        results["total"] = total_power

        return results

    def _calculate_array_power(
        self, array: ArrayConfig, solar_radiation: float
    ) -> float:
        """Calculate power output for a single array using pvlib GHI-to-POA conversion.

        Args:
            array: The array configuration
            solar_radiation: Solar radiation in W/m² (GHI from weather station)

        Returns:
            Estimated power output in watts
        """
        if solar_radiation <= 0:
            return 0.0

        try:
            # Get current solar position
            now = datetime.now(tz=ZoneInfo(self.hass.config.time_zone))
            solar_position = self.location.get_solarposition(now)
            # pvlib returns pandas Series, extract scalar values
            solar_zenith = float(solar_position["zenith"].iloc[0])  # type: ignore[union-attr]
            solar_azimuth = float(solar_position["azimuth"].iloc[0])  # type: ignore[union-attr]

            # Calculate angle of incidence
            aoi = pvlib.irradiance.aoi(
                surface_tilt=array.tilt,
                surface_azimuth=array.azimuth,
                solar_zenith=solar_zenith,
                solar_azimuth=solar_azimuth,
            )

            # Estimate DNI and DHI from GHI (simplified decomposition)
            # For better accuracy, use actual DNI/DHI sensors if available
            # This uses Erbs model approximation
            cos_zenith = max(0, pvlib.tools.cosd(solar_zenith))
            if cos_zenith > 0.01:  # Sun is above horizon
                # Rough estimate: DNI = GHI * cos(zenith), DHI = 15% of GHI
                # This is a simplification; proper models use clearness index
                dni = solar_radiation * cos_zenith
                dhi = solar_radiation * 0.15
            else:
                dni = 0.0
                dhi = solar_radiation

            # Convert GHI to POA using isotropic sky model
            poa_irradiance = pvlib.irradiance.get_total_irradiance(
                surface_tilt=array.tilt,
                surface_azimuth=array.azimuth,
                solar_zenith=solar_zenith,
                solar_azimuth=solar_azimuth,
                dni=dni,
                ghi=solar_radiation,
                dhi=dhi,
                model="isotropic",
            )
            # Extract scalar value from Series
            poa_series = poa_irradiance["poa_global"]
            poa_global = (
                float(poa_series.iloc[0])
                if hasattr(poa_series, "iloc")
                else float(poa_series)
            )  # type: ignore[arg-type]

            # Calculate power from POA irradiance
            power = float(
                (poa_global / STC_IRRADIANCE)
                * array.panel_wattage
                * self.inverter_efficiency
                * array.panel_count
            )

            # Debug logging
            _LOGGER.debug(
                "Array %s: GHI=%.2f W/m², zenith=%.1f°, azimuth=%.1f°, AOI=%.1f°, POA=%.2f W/m², power=%.2f W",
                array.name,
                solar_radiation,
                solar_zenith,
                solar_azimuth,
                aoi,
                poa_global,
                power,
            )

            return max(0.0, power)

        except (ValueError, ArithmeticError) as err:
            _LOGGER.error("Error calculating power for array %s: %s", array.name, err)
            return 0.0
