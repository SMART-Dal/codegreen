# Contributing to CodeGreen

Thank you for your interest in contributing to CodeGreen! This guide will help you get started.

## Quick Start

1. **Fork the Repository**
   ```bash
   # Fork on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/codegreen.git
   cd codegreen
   ```

2. **Set Up Development Environment**
   ```bash
   # Add upstream remote
   git remote add upstream https://github.com/codegreen/codegreen.git

   # Install dependencies
   ./install.sh

   # Or manual setup
   pip3 install -e ".[dev]"
   ```

3. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **Make Changes and Test**
   ```bash
   # Make your changes

   # Run tests
   pytest tests/
   cd build && ctest

   # Verify functionality
   codegreen doctor
   ```

5. **Submit Pull Request**
   ```bash
   git push origin feature/your-feature-name
   # Open PR on GitHub
   ```

## Development Workflow

### Branch Strategy

- **`main`**: Stable release branch
- **`develop`**: Integration branch for features
- **`feature/*`**: New features
- **`bugfix/*`**: Bug fixes
- **`hotfix/*`**: Urgent production fixes

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style/formatting
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Adding/updating tests
- `build`: Build system changes
- `ci`: CI/CD changes

**Examples:**
```bash
git commit -m "feat(nemb): add AMD ROCm GPU support"
git commit -m "fix(cli): resolve RAPL permission error on Ubuntu 22.04"
git commit -m "docs(examples): add Java energy profiling examples"
```

### Code Style

**C++ (NEMB):**
- Follow [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html)
- Use `clang-format` for formatting
- Header guards: `CODEGREEN_<PATH>_<FILE>_HPP`

```cpp
// Good
namespace codegreen {

class MeasurementCoordinator {
public:
    void start_measurement();

private:
    std::vector<std::unique_ptr<EnergyProvider>> providers_;
};

}  // namespace codegreen
```

**Python:**
- Follow [PEP 8](https://pep8.org/)
- Use `black` for formatting
- Use `ruff` for linting

```python
# Format code
black src/

# Lint code
ruff check src/
```

### Testing Requirements

All contributions must include tests:

**C++ Tests (Google Test):**
```cpp
// tests/nemb/test_measurement_coordinator.cpp
#include <gtest/gtest.h>
#include "nemb/core/measurement_coordinator.hpp"

TEST(MeasurementCoordinatorTest, StartStopMeasurement) {
    codegreen::MeasurementCoordinator coordinator;
    ASSERT_TRUE(coordinator.start());
    ASSERT_TRUE(coordinator.stop());
}
```

**Python Tests (pytest):**
```python
# tests/test_cli.py
def test_measure_command():
    result = subprocess.run(
        ["codegreen", "measure", "python", "test_script.py"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Energy" in result.stdout
```

**Run Tests:**
```bash
# C++ tests
cd build
cmake .. -DBUILD_TESTS=ON
make
ctest --output-on-failure

# Python tests
pytest tests/ -v

# Coverage
pytest tests/ --cov=src --cov-report=html
```

## Areas for Contribution

### 1. New Language Support

Add support for additional programming languages:

**Steps:**
1. Add Tree-sitter grammar to `third_party/`
2. Create language queries in `src/instrumentation/language_configs.py`
3. Add runtime wrapper in `runtime/`
4. Add tests and examples

**Example PR:** Adding Rust support

### 2. Hardware Sensor Drivers

Implement new energy measurement providers:

**Steps:**
1. Create provider class in `src/measurement/src/nemb/drivers/`
2. Implement `EnergyProvider` interface
3. Register in `MeasurementCoordinator`
4. Add configuration options
5. Document hardware requirements

**Example:** ARM Mali GPU support

### 3. Documentation Improvements

- Fix typos and unclear explanations
- Add usage examples
- Improve API documentation
- Translate to other languages

### 4. Bug Fixes

- Check [Issues](https://github.com/codegreen/codegreen/issues) for bugs
- Reproduce the issue
- Write failing test
- Implement fix
- Verify test passes

### 5. Performance Optimizations

- Profile measurement overhead
- Optimize hot paths
- Reduce memory allocations
- Benchmark improvements

## Code Review Process

1. **Automated Checks**
   - CI/CD pipeline runs automatically
   - All tests must pass
   - Code coverage should not decrease

2. **Review by Maintainers**
   - At least one maintainer approval required
   - Address review comments
   - Update code based on feedback

3. **Merge**
   - Squash commits if needed
   - Merge to `develop` branch
   - Delete feature branch

## Development Setup

### Required Tools

```bash
# Formatting tools
pip3 install black ruff

# Testing tools
pip3 install pytest pytest-cov

# C++ tools
sudo apt-get install clang-format clang-tidy
```

### Pre-commit Hooks

Install pre-commit hooks to automatically check code:

```bash
pip3 install pre-commit
pre-commit install
```

This runs before each commit:
- `black`: Python formatting
- `ruff`: Python linting
- `clang-format`: C++ formatting
- `pytest`: Python tests

### IDE Setup

**VS Code:**
```json
// .vscode/settings.json
{
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "C_Cpp.clang_format_style": "Google"
}
```

**CLion/PyCharm:**
- Enable Google C++ style
- Configure Black as Python formatter
- Enable Ruff linter

## Debugging

### Debug Build

```bash
mkdir build-debug && cd build-debug
cmake .. -DCMAKE_BUILD_TYPE=Debug
make -j$(nproc)
```

### GDB Debugging

```bash
# Debug the binary
gdb --args build-debug/bin/codegreen measure python test.py

# Common commands
(gdb) break codegreen_energy.cpp:123
(gdb) run
(gdb) backtrace
(gdb) print variable_name
```

### Python Debugging

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use debugger
python -m pdb src/cli/cli.py measure python test.py
```

## Reporting Issues

### Bug Reports

Include:
- CodeGreen version (`codegreen --version`)
- Operating system and version
- Hardware details (`codegreen info --verbose`)
- Steps to reproduce
- Expected vs actual behavior
- Error messages/logs

**Template:**
```markdown
**Bug Description**
Brief description of the issue

**To Reproduce**
1. Run `codegreen measure python script.py`
2. See error

**Expected Behavior**
Should measure energy without error

**Environment**
- CodeGreen version: 0.1.0
- OS: Ubuntu 22.04
- CPU: Intel i7-9750H
- Output of `codegreen doctor --verbose`

**Logs**
```
[error logs here]
```
```

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternative approaches considered
- Willingness to implement

## Getting Help

- **Documentation**: [docs.codegreen.io](https://docs.codegreen.io)
- **Discussions**: [GitHub Discussions](https://github.com/codegreen/codegreen/discussions)
- **Issues**: [GitHub Issues](https://github.com/codegreen/codegreen/issues)
- **Email**: dev@codegreen.io

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Recognition

Contributors are recognized in:
- `AUTHORS.md` file
- Release notes
- GitHub contributors page

Thank you for making CodeGreen better!
