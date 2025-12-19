"""Number platform for SolarMax integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfIrradiance
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .models import SolarMaxConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarMaxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SolarMax number entities."""
    async_add_entities([SolarRadiationNumber(entry)])


class SolarRadiationNumber(NumberEntity):
    """Number entity for manual solar radiation input."""

    _attr_has_entity_name = True
    _attr_name = "Solar radiation (manual)"
    _attr_native_min_value = 0
    _attr_native_max_value = 1500
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfIrradiance.WATTS_PER_SQUARE_METER
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:solar-power"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the number entity."""
        self._attr_unique_id = f"{entry.entry_id}_solar_radiation_manual"
        self._attr_native_value = 0.0

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()
