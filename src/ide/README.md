# Energy IDE

The **Energy IDE** module integrates CodeGreen with popular development environments. It offers IDE plugins and a user interface for triggering energy measurements, visualizing reports, and interacting with the tool.

**Responsibilities:**
- Provide integration with IDEs like VSCode and IntelliJ.
- Offer a unified UI for initiating measurements and displaying energy consumption reports.
- Decouple user interface components from the core measurement logic.

**Design Patterns:**
- **Facade Pattern:** Simplify user interactions with a unified control panel.
- **Adapter Pattern:** Integrate with different IDE ecosystems through plugin adapters.

**Usage and Extension:**
- Develop new IDE plugins by extending the base plugin framework provided.
- Customize UI components and reporting dashboards without affecting the underlying measurement system.

## Building

```bash
# From the project root
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make codegreen-ide
```

## Testing

```bash
# Run IDE tests
ctest -R ide
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your IDE integration
4. Add tests
5. Submit a pull request
