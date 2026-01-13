"""Data update coordinator for SolarMax integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pvlib
from pvlib.location import Location

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_NOCT,
    DOMAIN,
    STC_IRRADIANCE,
    STC_TEMPERATURE,
    UPDATE_INTERVAL,
)
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
        temperature_entity: str | None,
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
        self.temperature_entity = temperature_entity
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

        # Get temperature if available
        temperature: float | None = None
        if self.temperature_entity:
            temp_state = self.hass.states.get(self.temperature_entity)
            if temp_state and temp_state.state not in ("unknown", "unavailable"):
                try:
                    temperature = float(temp_state.state)
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid temperature value from %s: %s",
                        self.temperature_entity,
                        temp_state.state,
                    )

        # Calculate power output for each array
        results: dict[str, float] = {}
        total_power = 0.0
        for array in self.arrays:
            power = await self.hass.async_add_executor_job(
                self._calculate_array_power, array, solar_radiation, temperature
            )
            results[array.name] = power
            total_power += power

        # Apply inverter capacity clipping to total power
        total_power = min(total_power, self.inverter_capacity)
        results["total"] = total_power

        return results

    def _calculate_array_power(
        self, array: ArrayConfig, solar_radiation: float, temperature: float | None
    ) -> float:
        """Calculate power output for a single array using pvlib GHI-to-POA conversion.

        Args:
            array: The array configuration
            solar_radiation: Solar radiation in W/m² (GHI from weather station)
            temperature: Panel temperature in °C (optional)

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

            # Estimate DNI and DHI from GHI using pvlib's Erbs decomposition model
            # For better accuracy, use actual DNI/DHI sensors if available
            if solar_zenith < 87:  # Sun is meaningfully above horizon
                day_of_year = now.timetuple().tm_yday

                # Use Erbs model to decompose GHI into DNI and DHI
                erbs_result = pvlib.irradiance.erbs(
                    ghi=solar_radiation,
                    zenith=solar_zenith,
                    datetime_or_doy=day_of_year,
                )
                # Extract scalar values from result
                dni = float(erbs_result["dni"].iloc[0]) if hasattr(erbs_result["dni"], "iloc") else float(erbs_result["dni"])
                dhi = float(erbs_result["dhi"].iloc[0]) if hasattr(erbs_result["dhi"], "iloc") else float(erbs_result["dhi"])
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

            # Apply temperature coefficient if temperature is available
            temp_correction = 1.0
            panel_temperature = None
            if temperature is not None:
                # Estimate panel temperature from ambient air temperature
                # Using simplified NOCT model: T_cell = T_air + (NOCT - 20) / 800 * POA

                # Panel temperature rises above ambient based on irradiance
                # Typical panels run 20-30°C hotter than air on sunny days
                temp_rise = ((DEFAULT_NOCT - 20) / 800) * poa_global
                panel_temperature = temperature + temp_rise

                # Temperature coefficient is %/°C, convert to decimal
                temp_diff = panel_temperature - STC_TEMPERATURE
                temp_correction = 1.0 + (
                    array.temperature_coefficient / 100.0 * temp_diff
                )
                power *= temp_correction

            # Debug logging
            if panel_temperature is not None:
                _LOGGER.debug(
                    "Array %s: GHI=%.2f W/m², zenith=%.1f°, azimuth=%.1f°, AOI=%.1f°, POA=%.2f W/m², air=%.1f°C, panel=%.1f°C, temp_corr=%.3f, power=%.2f W",
                    array.name,
                    solar_radiation,
                    solar_zenith,
                    solar_azimuth,
                    aoi,
                    poa_global,
                    temperature,
                    panel_temperature,
                    temp_correction,
                    power,
                )
            else:
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
