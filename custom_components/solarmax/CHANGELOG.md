# SolarMax Integration Changelog

## Version 2.0.0 - NumPy 2.0 Compatible

### Major Changes
- **Multi-Array Support**: Complete rewrite to support multiple solar panel arrays
- **Professional Solar Calculations**: Integrated pvlib library for accurate solar position and irradiance calculations
- **NumPy 2.0 Compatibility**: Implemented lazy imports to avoid `np.Inf` deprecation issues

### Features
- Configure multiple independent solar arrays with different orientations
- Individual sensors for each array showing real-time power output
- Total power sensor combining all arrays
- Angle-of-incidence corrections using pvlib
- Solar position calculations based on latitude/longitude
- Modern Home Assistant patterns (DataUpdateCoordinator, typed ConfigEntry)

### Technical Improvements
- **Lazy Loading**: pvlib is imported only when needed to avoid blocking the event loop
- **Type Safety**: Full type hints throughout the codebase
- **Efficiency**: Renamed "efficiency" to "inverter_efficiency" for clarity
- **Simplified Configuration**: Removed redundant "panel_area" field (calculated from panels)

### Configuration Fields (Per Array)
- `array_name`: Unique identifier for the array
- `panel_wattage`: Rated power per panel in watts (e.g., 400W)
- `panel_count`: Number of panels in the array
- `panel_azimuth`: Direction the panels face (0=N, 90=E, 180=S, 270=W)
- `panel_tilt`: Angle from horizontal (0=flat, 90=vertical)
- `inverter_efficiency`: System efficiency as decimal (e.g., 0.96 for 96%)

### Migration from v1.x
See [MIGRATION.md](MIGRATION.md) for detailed migration instructions.

### Breaking Changes
- Configuration format completely changed (config flow now manages arrays)
- Sensor entity IDs changed (now includes array names)
- "efficiency" field renamed to "inverter_efficiency"
- "panel_area" field removed (no longer needed)

### Dependencies
- `pvlib==0.10.3`: Professional solar calculations library
- Requires NumPy (automatically installed with pvlib)

### Known Issues
- pvlib 0.10.3 has deprecation warnings with NumPy 2.0
  - Mitigated by lazy imports (import only when calculations run)
  - Consider upgrading pvlib when newer version available
