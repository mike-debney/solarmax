"""Config flow for SolarMax integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

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
    CONF_TEMPERATURE_COEFFICIENT,
    CONF_TEMPERATURE_ENTITY,
    DEFAULT_INVERTER_CAPACITY,
    DEFAULT_INVERTER_EFFICIENCY,
    DEFAULT_PANEL_AZIMUTH,
    DEFAULT_PANEL_COUNT,
    DEFAULT_PANEL_TILT,
    DEFAULT_PANEL_WATTAGE,
    DEFAULT_TEMPERATURE_COEFFICIENT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def get_array_schema(array_data: dict[str, Any] | None = None) -> vol.Schema:
    """Get the array configuration schema."""
    if array_data is None:
        array_data = {}

    return vol.Schema(
        {
            vol.Required(
                CONF_ARRAY_NAME, default=array_data.get(CONF_ARRAY_NAME, "Array 1")
            ): cv.string,
            vol.Required(
                CONF_PANEL_WATTAGE,
                default=array_data.get(CONF_PANEL_WATTAGE, DEFAULT_PANEL_WATTAGE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=1000, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_PANEL_COUNT,
                default=array_data.get(CONF_PANEL_COUNT, DEFAULT_PANEL_COUNT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=10000, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_PANEL_AZIMUTH,
                default=array_data.get(CONF_PANEL_AZIMUTH, DEFAULT_PANEL_AZIMUTH),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=359, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_PANEL_TILT,
                default=array_data.get(CONF_PANEL_TILT, DEFAULT_PANEL_TILT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=90, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_TEMPERATURE_COEFFICIENT,
                default=array_data.get(
                    CONF_TEMPERATURE_COEFFICIENT, DEFAULT_TEMPERATURE_COEFFICIENT
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-1.0,
                    max=0.0,
                    step=0.01,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


class SolarMaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SolarMax."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._arrays: list[dict[str, Any]] = []
        self._array_index: int | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the solar radiation entity exists
            entity_id = user_input[CONF_SOLAR_RADIATION_ENTITY]
            if not self.hass.states.get(entity_id):
                errors[CONF_SOLAR_RADIATION_ENTITY] = "entity_not_found"
            else:
                # Store the initial data
                self._data = user_input
                # Get home location if not provided
                if CONF_LATITUDE not in self._data:
                    self._data[CONF_LATITUDE] = self.hass.config.latitude
                    self._data[CONF_LONGITUDE] = self.hass.config.longitude
                return await self.async_step_array()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="SolarMax"): cv.string,
                    vol.Required(CONF_SOLAR_RADIATION_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "input_number"])
                    ),
                    vol.Required(
                        CONF_INVERTER_EFFICIENCY,
                        default=DEFAULT_INVERTER_EFFICIENCY,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.01,
                            max=100,
                            step=0.01,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_INVERTER_CAPACITY,
                        default=DEFAULT_INVERTER_CAPACITY,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=1000000,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_array(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle configuring a solar array."""
        if user_input is not None:
            # Ensure temperature_coefficient has a value
            if CONF_TEMPERATURE_COEFFICIENT not in user_input:
                user_input[CONF_TEMPERATURE_COEFFICIENT] = (
                    DEFAULT_TEMPERATURE_COEFFICIENT
                )

            if self._array_index is not None:
                # Editing existing array - merge to preserve all fields
                self._arrays[self._array_index] = {
                    **self._arrays[self._array_index],
                    **user_input,
                }
                self._array_index = None
            else:
                # Adding new array
                self._arrays.append(user_input)

            # Ask if user wants to add another array
            return await self.async_step_add_another()

        # Get default name for new array
        array_data = (
            self._arrays[self._array_index]
            if self._array_index is not None
            else {CONF_ARRAY_NAME: f"Array {len(self._arrays) + 1}"}
        )

        return self.async_show_form(
            step_id="array",
            data_schema=get_array_schema(array_data),
            description_placeholders={
                "radiation_entity": self._data[CONF_SOLAR_RADIATION_ENTITY]
            },
        )

    async def async_step_add_another(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask if user wants to add another array."""
        if user_input is not None:
            if user_input.get("add_another"):
                return await self.async_step_array()

            # Finalize the configuration
            await self.async_set_unique_id(
                f"{self._data[CONF_SOLAR_RADIATION_ENTITY]}_solarmax"
            )
            self._abort_if_unique_id_configured()

            self._data[CONF_ARRAYS] = self._arrays

            return self.async_create_entry(
                title=self._data[CONF_NAME],
                data=self._data,
            )

        return self.async_show_form(
            step_id="add_another",
            data_schema=vol.Schema(
                {
                    vol.Required("add_another", default=False): cv.boolean,
                }
            ),
            description_placeholders={"array_count": str(len(self._arrays))},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SolarMaxOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SolarMaxOptionsFlowHandler(config_entry)


class SolarMaxOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for SolarMax integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self._arrays: list[dict[str, Any]] = []
        self._array_index: int | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "arrays":
                return await self.async_step_manage_arrays()
            if action == "inverter":
                return await self.async_step_edit_inverter()
            if action == "sensor":
                return await self.async_step_edit_sensor()
            if action == "temperature":
                return await self.async_step_edit_temperature()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "arrays": "Manage solar arrays",
                            "inverter": "Edit inverter settings",
                            "sensor": "Change solar radiation sensor",
                            "temperature": "Configure temperature sensor",
                        }
                    ),
                }
            ),
        )

    async def async_step_manage_arrays(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage solar arrays."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "add":
                return await self.async_step_add_array()
            if action == "edit":
                return await self.async_step_select_array_to_edit()
            if action == "delete":
                return await self.async_step_select_array_to_delete()
            if action == "done":
                # Save changes
                if self._arrays:
                    new_data = {**self.config_entry.data, CONF_ARRAYS: self._arrays}
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=new_data
                    )
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )
                return await self.async_step_init()

        # Initialize arrays from config entry only if not already loaded
        if not self._arrays:
            self._arrays = list(self.config_entry.data.get(CONF_ARRAYS, []))

        return self.async_show_form(
            step_id="manage_arrays",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "add": "Add new array",
                            "edit": "Edit existing array",
                            "delete": "Delete array",
                            "done": "Done",
                        }
                    ),
                }
            ),
            description_placeholders={"array_count": str(len(self._arrays))},
        )

    async def async_step_add_array(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new array."""
        if user_input is not None:
            # Ensure temperature_coefficient has a value
            if CONF_TEMPERATURE_COEFFICIENT not in user_input:
                user_input[CONF_TEMPERATURE_COEFFICIENT] = (
                    DEFAULT_TEMPERATURE_COEFFICIENT
                )
            self._arrays.append(user_input)
            return await self.async_step_manage_arrays()

        return self.async_show_form(
            step_id="add_array",
            data_schema=get_array_schema(
                {CONF_ARRAY_NAME: f"Array {len(self._arrays) + 1}"}
            ),
        )

    async def async_step_select_array_to_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select an array to edit."""
        if user_input is not None:
            self._array_index = int(user_input["array_index"])
            return await self.async_step_edit_array()

        if not self._arrays:
            return await self.async_step_manage_arrays()

        array_options = {
            str(i): array[CONF_ARRAY_NAME] for i, array in enumerate(self._arrays)
        }

        return self.async_show_form(
            step_id="select_array_to_edit",
            data_schema=vol.Schema(
                {
                    vol.Required("array_index"): vol.In(array_options),
                }
            ),
        )

    async def async_step_edit_array(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit an existing array."""
        if user_input is not None:
            if self._array_index is not None:
                # Start with existing array data
                updated_array = self._arrays[self._array_index].copy()
                # Update with all fields from user_input
                updated_array.update(user_input)
                self._arrays[self._array_index] = updated_array
                self._array_index = None
            return await self.async_step_manage_arrays()

        array_data = (
            self._arrays[self._array_index] if self._array_index is not None else {}
        )

        return self.async_show_form(
            step_id="edit_array",
            data_schema=get_array_schema(array_data),
        )

    async def async_step_select_array_to_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select an array to delete."""
        if user_input is not None:
            array_index = int(user_input["array_index"])
            self._arrays.pop(array_index)
            return await self.async_step_manage_arrays()

        if not self._arrays:
            return await self.async_step_manage_arrays()

        array_options = {
            str(i): array[CONF_ARRAY_NAME] for i, array in enumerate(self._arrays)
        }

        return self.async_show_form(
            step_id="select_array_to_delete",
            data_schema=vol.Schema(
                {
                    vol.Required("array_index"): vol.In(array_options),
                }
            ),
        )

    async def async_step_edit_inverter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit inverter settings."""
        if user_input is not None:
            new_data = {
                **self.config_entry.data,
                CONF_INVERTER_EFFICIENCY: user_input[CONF_INVERTER_EFFICIENCY],
                CONF_INVERTER_CAPACITY: user_input[CONF_INVERTER_CAPACITY],
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="edit_inverter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INVERTER_EFFICIENCY,
                        default=self.config_entry.data.get(
                            CONF_INVERTER_EFFICIENCY, DEFAULT_INVERTER_EFFICIENCY
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=100, step=1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_INVERTER_CAPACITY,
                        default=self.config_entry.data.get(
                            CONF_INVERTER_CAPACITY, DEFAULT_INVERTER_CAPACITY
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=1000000, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit solar radiation sensor."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the solar radiation entity exists
            entity_id = user_input[CONF_SOLAR_RADIATION_ENTITY]
            if not self.hass.states.get(entity_id):
                errors[CONF_SOLAR_RADIATION_ENTITY] = "entity_not_found"
            else:
                new_data = {
                    **self.config_entry.data,
                    CONF_SOLAR_RADIATION_ENTITY: entity_id,
                }
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="edit_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SOLAR_RADIATION_ENTITY,
                        default=self.config_entry.data.get(CONF_SOLAR_RADIATION_ENTITY),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "input_number"])
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_edit_temperature(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit temperature sensor."""
        if user_input is not None:
            # Temperature sensor is optional, so we don't validate it exists
            new_data = {
                **self.config_entry.data,
                CONF_TEMPERATURE_ENTITY: user_input.get(CONF_TEMPERATURE_ENTITY),
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="edit_temperature",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TEMPERATURE_ENTITY,
                        default=self.config_entry.data.get(CONF_TEMPERATURE_ENTITY),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "input_number"])
                    ),
                }
            ),
        )
