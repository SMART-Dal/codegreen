//! Code instrumentation tools for energy measurement
//! 
//! This package provides tools for instrumenting code to measure energy consumption
//! across different programming languages.

use std::path::Path;
use hardware_plugins::HardwarePlugin;
use crate::error::InstrumentationError;

pub mod error;
pub mod hardware;
pub mod metrics;
pub mod parser;

use hardware::EnergyMonitor;
use metrics::MetricsStore;
use parser::InstrumentationParser;

pub struct InstrumentationConfig {
    pub influxdb_url: String,
    pub influxdb_database: String,
}

pub struct Instrumenter {
    config: InstrumentationConfig,
    monitor: EnergyMonitor,
    metrics: MetricsStore,
    parser: InstrumentationParser,
}

impl Instrumenter {
    pub fn new(config: InstrumentationConfig) -> Result<Self, InstrumentationError> {
        let monitor = EnergyMonitor::new();
        let metrics = MetricsStore::new(&config.influxdb_url, &config.influxdb_database)?;
        let parser = InstrumentationParser::new();

        Ok(Self {
            config,
            monitor,
            metrics,
            parser,
        })
    }

    pub fn register_plugin(&mut self, plugin: Box<dyn HardwarePlugin>) {
        self.monitor.register_plugin(plugin);
    }

    pub async fn instrument_file(&mut self, path: &Path) -> Result<(), InstrumentationError> {
        let source = tokio::fs::read_to_string(path).await?;
        let _tree = self.parser.parse(&source)?;

        // Start energy measurement
        self.monitor.start_measurement().await?;

        // Process the file
        // TODO: Implement actual instrumentation logic

        // Stop measurement and record results
        let measurements = self.monitor.stop_measurement().await?;
        for measurement in &measurements {
            self.metrics.record_measurement(measurement).await?;
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_instrumenter_creation() {
        let config = InstrumentationConfig {
            influxdb_url: "http://localhost:8086".to_string(),
            influxdb_database: "test".to_string(),
        };
        let instrumenter = Instrumenter::new(config).unwrap();
        assert!(instrumenter.monitor.plugins.is_empty());
    }
} 