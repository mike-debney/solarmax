"""Constants for the SolarMax integration."""

DOMAIN = "solarmax"

# Configuration
CONF_SOLAR_RADIATION_ENTITY = "solar_radiation_entity"
CONF_ARRAYS = "arrays"
CONF_ARRAY_NAME = "array_name"
CONF_PANEL_WATTAGE = "panel_wattage"
CONF_PANEL_COUNT = "panel_count"
CONF_PANEL_AZIMUTH = "panel_azimuth"
CONF_PANEL_TILT = "panel_tilt"
CONF_INVERTER_EFFICIENCY = "inverter_efficiency"
CONF_INVERTER_CAPACITY = "inverter_capacity"

# Defaults
DEFAULT_PANEL_WATTAGE = 400
DEFAULT_PANEL_COUNT = 1
DEFAULT_PANEL_AZIMUTH = 180  # South
DEFAULT_PANEL_TILT = 30
DEFAULT_INVERTER_EFFICIENCY = 96
DEFAULT_INVERTER_CAPACITY = 5000

# Standard test conditions (STC)
STC_IRRADIANCE = 1000  # W/m²

# Update interval
UPDATE_INTERVAL = 60  # seconds
