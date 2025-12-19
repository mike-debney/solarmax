"""Data update coordinator for SolarMax integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any
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
    def location(self) -> Any:
        """Get pvlib Location object (lazy loaded)."""
        if self._location is None:
            from pvlib.location import Location  # noqa: PLC0415

            self._location = Location(latitude=self.latitude, longitude=self.longitude)
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
            # Clip individual array power to inverter capacity
            power = min(power, self.inverter_capacity)
            results[array.name] = power
            total_power += power

        # Apply inverter capacity clipping to total power
        total_power = min(total_power, self.inverter_capacity)
        results["total"] = total_power

        return results

    def _calculate_array_power(
        self, array: ArrayConfig, solar_radiation: float
    ) -> float:
        """Calculate power output for a single array using pvlib.

        Args:
            array: The array configuration
            solar_radiation: Solar radiation in W/m²

        Returns:
            Estimated power output in watts
        """
        if solar_radiation <= 0:
            return 0.0

        try:
            # Lazy import pvlib to avoid blocking event loop at module load
            import pvlib  # noqa: PLC0415

            # Get current time in UTC
            now = datetime.now(tz=ZoneInfo("UTC"))

            # Calculate solar position
            solar_position = self.location.get_solarposition(now)

            # Calculate the angle of incidence
            aoi = pvlib.irradiance.aoi(
                surface_tilt=array.tilt,
                surface_azimuth=array.azimuth,
                solar_zenith=solar_position["apparent_zenith"].iloc[0],
                solar_azimuth=solar_position["azimuth"].iloc[0],
            )

            # Calculate effective irradiance accounting for angle of incidence
            # This uses the cosine of the angle of incidence to adjust the measured radiation
            effective_irradiance = solar_radiation * max(0, pvlib.tools.cosd(aoi))

            # Debug logging
            _LOGGER.debug(
                "Array %s: radiation=%.2f, aoi=%.2f, effective=%.2f, zenith=%.2f, efficiency=%.2f",
                array.name,
                solar_radiation,
                aoi,
                effective_irradiance,
                solar_position["apparent_zenith"].iloc[0],
                self.inverter_efficiency,
            )

            # Calculate power output
            # Power = (Effective Irradiance / STC Irradiance) × Rated Power × Inverter Efficiency × Panel Count
            power = float(
                (effective_irradiance / STC_IRRADIANCE)
                * array.panel_wattage
                * self.inverter_efficiency
                * array.panel_count
            )

            _LOGGER.debug("Array %s: calculated power=%.2f W", array.name, power)

            return max(0.0, power)

        except (ValueError, ArithmeticError) as err:
            _LOGGER.error("Error calculating power for array %s: %s", array.name, err)
            return 0.0
