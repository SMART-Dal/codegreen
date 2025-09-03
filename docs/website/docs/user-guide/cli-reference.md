# CLI Reference

Complete reference for CodeGreen command-line interface.

## Global Options

```bash
codegreen [OPTIONS] COMMAND [ARGS]...
```

### Options

- `--debug`: Enable debug output
- `--config PATH`: Path to configuration file
- `--version, -v`: Show version and exit
- `--log-level [DEBUG|INFO|WARNING|ERROR]`: Set logging level
- `--help, -h`: Show help message

## Commands

### `init`

Initialize and cache sensor configuration.

```bash
codegreen init [OPTIONS]
```

**Options:**
- `--force`: Force re-initialization
- `--cache-path PATH`: Custom cache file path

### `measure`

Measure energy consumption of a script.

```bash
codegreen measure [OPTIONS] COMMAND [ARGS]...
```

**Options:**
- `--precision [low|medium|high]`: Measurement precision
- `--timeout SECONDS`: Maximum measurement time
- `--output FORMAT`: Output format (json, table, csv)
- `--save`: Save results to file
- `--verbose`: Detailed output

**Examples:**
```bash
codegreen measure python script.py
codegreen measure --precision high --timeout 60 python script.py
```

### `info`

Display CodeGreen installation information.

```bash
codegreen info [OPTIONS]
```

### `doctor`

Diagnose CodeGreen installation and configuration.

```bash
codegreen doctor [OPTIONS]
```

### `config`

Manage CodeGreen configuration.

```bash
codegreen config COMMAND [OPTIONS]
```

**Subcommands:**
- `show`: Display current configuration
- `validate`: Validate configuration file
- `reset`: Reset to default configuration
