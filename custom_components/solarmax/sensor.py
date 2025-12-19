"""Sensor platform for SolarMax integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarMaxCoordinator
from .models import ArrayConfig, SolarMaxConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SolarMaxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SolarMax sensor based on a config entry."""
    runtime_data = config_entry.runtime_data
    coordinator = runtime_data.coordinator
    arrays = runtime_data.arrays

    entities: list[SensorEntity] = []

    # Create sensor for total power output
    entities.append(
        SolarMaxTotalSensor(
            coordinator=coordinator,
            config_entry=config_entry,
        )
    )

    # Create sensor for each array
    entities.extend(
        SolarMaxArraySensor(
            coordinator=coordinator,
            config_entry=config_entry,
            array=array,
        )
        for array in arrays
    )

    async_add_entities(entities)


class SolarMaxTotalSensor(CoordinatorEntity[SolarMaxCoordinator], SensorEntity):
    """Representation of total solar power output sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_has_entity_name = True
    _attr_translation_key = "total_solar_output"

    def __init__(
        self,
        coordinator: SolarMaxCoordinator,
        config_entry: SolarMaxConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_total"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="SolarMax Estimator",
            manufacturer="SolarMax",
            model="Solar Array Estimator",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("total")

    @property
    def extra_state_attributes(self) -> dict[str, str | int | float]:
        """Return additional state attributes."""
        arrays = self.coordinator.arrays
        total_capacity = sum(array.total_capacity for array in arrays)

        return {
            "solar_radiation_entity": self.coordinator.solar_radiation_entity,
            "array_count": len(arrays),
            "total_array_capacity": total_capacity,
        }


class SolarMaxArraySensor(CoordinatorEntity[SolarMaxCoordinator], SensorEntity):
    """Representation of individual solar array power output sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_has_entity_name = True
    _attr_translation_key = "array_solar_output"

    def __init__(
        self,
        coordinator: SolarMaxCoordinator,
        config_entry: SolarMaxConfigEntry,
        array: ArrayConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._array = array
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{array.name.lower().replace(' ', '_')}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="SolarMax Estimator",
            manufacturer="SolarMax",
            model="Solar Array Estimator",
        )
        # Set the entity name to the array name
        self._attr_name = array.name

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._array.name)

    @property
    def extra_state_attributes(self) -> dict[str, str | int | float]:
        """Return additional state attributes."""
        return {
            "panel_wattage": self._array.panel_wattage,
            "panel_count": self._array.panel_count,
            "azimuth": self._array.azimuth,
            "tilt": self._array.tilt,
            "array_capacity": self._array.total_capacity,
        }
