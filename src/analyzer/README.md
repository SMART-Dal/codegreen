# Energy Visualization

The **Energy Visualization** module provides dynamic dashboards and visualization tools to analyze and display energy consumption data. It is designed to work seamlessly with the reporting module and offers customizable visual components such as charts, graphs, and dashboards.

## Responsibilities
- Generate dynamic visualizations for energy consumption data.
- Offer filtering and drill-down capabilities.
- Integrate with the core reporting engine to visualize aggregated results.

## Design Patterns
- **Modular UI Components:** Enables reuse and customization of visualization elements.
- **Separation of Concerns:** Keeps visualization logic separate from data collection and reporting.

## Building

```bash
# From the project root
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make codegreen-visualization
```

## Testing

```bash
# Run visualization tests
ctest -R visualization
```

## Usage

```cpp
#include "visualization.hpp"

auto viz = std::make_unique<codegreen::Visualization>();

// Generate charts
bool success = viz->generate_charts(measurement_session);

// Generate reports
std::string report = viz->generate_report(measurement_session);

// Export data
bool exported = viz->export_data(measurement_session, "csv");
```

## Usage and Extension
- Use the provided dashboard components to build interactive reports.
- Extend the module by adding new visualization types or integrating with third-party charting libraries.
- Follow the provided guidelines in the `docs/` folder for contributing new visualization features.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your visualization features
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details
