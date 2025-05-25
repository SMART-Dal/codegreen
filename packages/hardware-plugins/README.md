# Energy Hardware Plugins

This package provides hardware-specific energy measurement plugins for CodeGreen. It implements a plugin architecture that allows for easy addition of new hardware measurement capabilities.

## Architecture

The package follows a plugin-based architecture where each hardware-specific implementation:
1. Implements the `HardwarePlugin` trait
2. Provides hardware-specific measurement logic
3. Exposes a consistent interface for energy measurement

## Available Plugins

### Intel RAPL Plugin
- Measures CPU package and DRAM energy consumption
- Uses Model Specific Registers (MSR) for measurements
- Requires root access to `/dev/cpu/*/msr`
- Supports power and energy measurements

## Adding New Plugins

To add a new hardware plugin:

1. Create a new module in `src/plugins/`
2. Implement the `HardwarePlugin` trait
3. Add the plugin to `src/plugins/mod.rs`
4. Register the plugin in the `PluginRegistry`

Example:
```rust
use energy_hardware_plugins::{HardwarePlugin, HardwareError, Measurement};

pub struct MyHardwarePlugin {
    // Plugin-specific fields
}

impl HardwarePlugin for MyHardwarePlugin {
    // Implement required methods
}
```

## Usage

```rust
use energy_hardware_plugins::{PluginRegistry, IntelRAPLPlugin};

let mut registry = PluginRegistry::new();
registry.register_plugin(Box::new(IntelRAPLPlugin::new()));

// Get available plugins
let available_plugins = registry.get_available_plugins();

// Use a specific plugin
if let Some(plugin) = registry.get_plugin_by_name("intel_rapl") {
    plugin.initialize()?;
    plugin.start_measurement()?;
    let measurement = plugin.get_measurement()?;
    plugin.stop_measurement()?;
}
```

## Requirements

- Linux operating system
- Root access for hardware sensors
- Appropriate hardware support (e.g., Intel CPU for RAPL)

## Testing

Run the tests with:
```bash
cargo test
```

Note: Some tests require hardware support and may be skipped if the required hardware is not available.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your plugin
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details
