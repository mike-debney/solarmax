"""The SolarMax integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)

from .const import (
    CONF_ARRAY_NAME,
    CONF_ARRAYS,
    CONF_INVERTER_CAPACITY,
    CONF_INVERTER_EFFICIENCY,
    CONF_PANEL_AZIMUTH,
    CONF_PANEL_COUNT,
    CONF_PANEL_TILT,
    CONF_PANEL_WATTAGE,
    CONF_SOLAR_RADIATION_ENTITY,
)
from .coordinator import SolarMaxCoordinator
from .models import ArrayConfig, SolarMaxConfigEntry, SolarMaxRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["number", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: SolarMaxConfigEntry) -> bool:
    """Set up SolarMax from a config entry."""
    # Convert arrays configuration to ArrayConfig objects
    arrays_data = entry.data.get(CONF_ARRAYS, [])
    arrays = [
        ArrayConfig(
            name=array_data[CONF_ARRAY_NAME],
            panel_wattage=array_data[CONF_PANEL_WATTAGE],
            panel_count=array_data[CONF_PANEL_COUNT],
            azimuth=array_data[CONF_PANEL_AZIMUTH],
            tilt=array_data[CONF_PANEL_TILT],
        )
        for array_data in arrays_data
    ]

    # Create coordinator
    coordinator = SolarMaxCoordinator(
        hass=hass,
        config_entry=entry,
        arrays=arrays,
        solar_radiation_entity=entry.data[CONF_SOLAR_RADIATION_ENTITY],
        latitude=entry.data.get(CONF_LATITUDE, hass.config.latitude),
        longitude=entry.data.get(CONF_LONGITUDE, hass.config.longitude),
        inverter_efficiency=entry.data[CONF_INVERTER_EFFICIENCY],
        inverter_capacity=entry.data[CONF_INVERTER_CAPACITY],
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data
    entry.runtime_data = SolarMaxRuntimeData(
        coordinator=coordinator,
        arrays=arrays,
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for state changes of the solar radiation sensor
    @callback
    def _async_solar_radiation_updated(event: Event[EventStateChangedData]) -> None:
        """Handle solar radiation sensor state changes."""
        hass.async_create_task(coordinator.async_request_refresh())

    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            entry.data[CONF_SOLAR_RADIATION_ENTITY],
            _async_solar_radiation_updated,
        )
    )

    # Add update listener for config changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolarMaxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: SolarMaxConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
