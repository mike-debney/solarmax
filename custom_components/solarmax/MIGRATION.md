# SolarMax Integration Migration Guide

## Overview of Changes

The SolarMax integration has been completely rewritten to support multiple solar arrays with individual and combined power output sensors, using the `pvlib` library for more accurate solar calculations.

## Breaking Changes ⚠️

**Version 2.0.0 introduces breaking changes. Existing installations will need to be reconfigured.**

### What Changed

1. **Configuration Structure**: Arrays are now stored in a list format instead of single panel configuration
2. **Entity IDs**: New entity naming scheme for individual arrays
3. **Attributes**: Panel direction renamed to azimuth for clarity
4. **Dependencies**: Now requires `pvlib` library

### Migration Steps

If you have an existing SolarMax installation:

1. **Note your current configuration** (panel specs, direction, tilt, etc.)
2. **Remove the old integration** from Settings → Devices & Services
3. **Restart Home Assistant**
4. **Add the integration again** and configure your array(s)
5. **Update any automations or scripts** that reference the old entity IDs

## New Architecture

### File Structure

```
custom_components/solarmax/
├── __init__.py          # Integration setup with coordinator initialization
├── manifest.json        # Updated with pvlib dependency (v2.0.0)
├── const.py            # Constants with array-specific configs
├── models.py           # NEW: Data models (ArrayConfig, RuntimeData)
├── coordinator.py      # NEW: DataUpdateCoordinator for centralized updates
├── config_flow.py      # Enhanced for multi-array management
├── sensor.py           # Rewritten for multiple array sensors
├── strings.json        # Updated with new UI strings
└── README.md           # NEW: Comprehensive documentation
```

### Key Components

#### 1. Models (`models.py`)
- `ArrayConfig`: Dataclass for array configuration
- `SolarMaxRuntimeData`: Runtime data container
- `SolarMaxConfigEntry`: Typed config entry

#### 2. Coordinator (`coordinator.py`)
- Uses `DataUpdateCoordinator` pattern
- Integrates pvlib for solar position calculations
- Handles angle-of-incidence corrections
- Updates every 60 seconds (configurable)

#### 3. Enhanced Config Flow
- Multi-step setup process
- Add/edit/delete arrays via options flow
- Better validation and error handling

#### 4. Multiple Sensors
- One total power sensor (sum of all arrays)
- Individual sensor per array
- Detailed attributes for each sensor

## Configuration Examples

### Old Configuration (v1.0.0)
```yaml
# Single array only
panel_wattage: 400
panel_count: 20
panel_direction: 180  # degrees
panel_tilt: 30
efficiency: 0.85
```

### New Configuration (v2.0.0)
```yaml
# Supports multiple arrays
arrays:
  - array_name: "Main Roof"
    panel_wattage: 400
    panel_count: 15
    panel_azimuth: 180  # renamed from direction
    panel_tilt: 30
    efficiency: 0.85

  - array_name: "East Garage"
    panel_wattage: 350
    panel_count: 8
    panel_azimuth: 90
    panel_tilt: 20
    efficiency: 0.85
```

## Technical Improvements

### 1. pvlib Integration
The integration now uses pvlib for more accurate calculations:

```python
# Calculate solar position
solar_position = location.get_solarposition(timestamp)

# Calculate angle of incidence
aoi = pvlib.irradiance.aoi(
    surface_tilt=array.tilt,
    surface_azimuth=array.azimuth,
    solar_zenith=solar_position["apparent_zenith"],
    solar_azimuth=solar_position["azimuth"],
)

# Apply cosine correction for effective irradiance
effective_irradiance = solar_radiation * max(0, pvlib.tools.cosd(aoi))
```

### 2. DataUpdateCoordinator Pattern
Centralized data updates following Home Assistant best practices:

```python
class SolarMaxCoordinator(DataUpdateCoordinator[dict[str, float]]):
    async def _async_update_data(self) -> dict[str, float]:
        # Fetch solar radiation once
        # Calculate power for all arrays
        # Return dictionary with array_name: power_output
```

### 3. Runtime Data Storage
Uses `ConfigEntry.runtime_data` instead of `hass.data`:

```python
entry.runtime_data = SolarMaxRuntimeData(
    coordinator=coordinator,
    arrays=arrays,
)
```

### 4. Typed Configuration
Type-safe configuration using Python type hints:

```python
type SolarMaxConfigEntry = ConfigEntry[SolarMaxRuntimeData]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarMaxConfigEntry
) -> bool:
    # Full IDE autocomplete and type checking
```

## Entity Changes

### Old Entities (v1.0.0)
- `sensor.solarmax_estimator_estimated_solar_output`

### New Entities (v2.0.0)
- `sensor.solarmax_estimator_total_estimated_solar_output` (total)
- `sensor.solarmax_estimator_{array_name}` (one per array)

### Attribute Changes

**Old attributes:**
```yaml
solar_radiation_entity: sensor.solar_radiation
panel_wattage: 400
panel_area: 2.0
panel_count: 20
panel_direction: 180  # changed to azimuth
panel_tilt: 30
efficiency: 0.85
total_array_capacity: 8000
```

**New attributes (Total sensor):**
```yaml
solar_radiation_entity: sensor.solar_radiation
array_count: 2
total_array_capacity: 8800
```

**New attributes (Array sensor):**
```yaml
panel_wattage: 400
panel_area: 2.0
panel_count: 15
azimuth: 180  # renamed from direction
tilt: 30
efficiency: 0.85
array_capacity: 6000
```

## Benefits of New Design

1. **Multiple Array Support**: Track different roof orientations independently
2. **More Accurate**: pvlib provides professional-grade solar calculations
3. **Better Performance**: Coordinator pattern reduces unnecessary updates
4. **Easier Maintenance**: Typed code with better error handling
5. **Flexible Configuration**: Add/remove arrays without recreating integration
6. **Individual Monitoring**: See performance of each array separately
7. **Total Overview**: Combined sensor for overall system production

## Testing Recommendations

After upgrading:

1. **Verify sensor data**: Check that power estimates are reasonable
2. **Compare with reality**: If you have a solar inverter, compare estimates
3. **Test multiple arrays**: Ensure individual and total sensors update correctly
4. **Check automations**: Update any references to old entity IDs
5. **Monitor logs**: Watch for any errors during updates

## Support

For issues or questions:
- Check the README.md for troubleshooting tips
- Review Home Assistant logs for errors
- Verify solar radiation sensor is providing valid W/m² values

## Development Notes

### Code Quality
- Follows Home Assistant coding standards
- Type hints throughout
- Proper error handling
- Uses async patterns correctly
- Passes ruff linting

### Future Enhancements
Potential future additions:
- Historical performance tracking
- Shading calculations
- Temperature derating
- Weather forecast integration
- ML-based efficiency adjustments

---

**Version**: 2.0.0
**Date**: December 2025
**Python**: 3.13+
**Home Assistant**: 2024.1+
