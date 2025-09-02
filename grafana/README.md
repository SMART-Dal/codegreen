# CodeGreen Grafana Dashboard

This directory contains Grafana dashboard templates for visualizing CodeGreen energy measurement data.

## Dashboard Features

The `codegreen-dashboard.json` provides comprehensive energy monitoring with the following panels:

1. **Total Energy Consumption by Session** - Shows total energy consumption for each measurement session
2. **Session Duration** - Displays the duration of each measurement session
3. **Energy Consumption Timeline** - Time series visualization of energy consumption at each checkpoint
4. **Energy by Function** - Pie chart showing energy distribution across different functions
5. **Energy by Programming Language** - Bar gauge comparing energy consumption by language
6. **Top Energy Consuming Files** - Table listing the most energy-intensive files

## Setup Instructions

### Prerequisites
- Grafana server running (version 8.0+)
- Prometheus server configured to scrape CodeGreen metrics
- CodeGreen Prometheus exporter running

### Import Dashboard

1. Open Grafana web interface
2. Navigate to "+" → "Import"
3. Upload the `codegreen-dashboard.json` file
4. Configure data source (Prometheus) if not already set
5. Save dashboard

### Prometheus Configuration

Add the following to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'codegreen'
    static_configs:
      - targets: ['localhost:8080']  # CodeGreen Prometheus exporter port
    scrape_interval: 5s
    metrics_path: '/metrics'
```

### Dashboard Variables

The dashboard supports the following variables for filtering:

- **session_id**: Filter by specific measurement session
- **language**: Filter by programming language (Python, C++, Java, C)
- **file_path**: Filter by specific source files

## Metrics Reference

The dashboard uses these Prometheus metrics from CodeGreen:

- `codegreen_session_total_energy_joules`: Total energy consumption per session
- `codegreen_session_duration_seconds`: Duration of measurement sessions
- `codegreen_checkpoint_energy_joules`: Energy consumption at individual checkpoints

## Customization

To customize the dashboard:

1. Modify panel queries in Grafana UI
2. Export updated dashboard JSON
3. Save changes to this file
4. Version control the updated dashboard

## Alerts Configuration

Consider setting up alerts for:

- High energy consumption (>10 joules per session)
- Long-running sessions (>5 minutes)
- Unusual energy spikes in specific functions

Example alert rule:
```yaml
- alert: HighEnergyConsumption
  expr: codegreen_session_total_energy_joules > 10
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "High energy consumption detected"
    description: "Session {{ $labels.session_id }} consumed {{ $value }} joules"
```