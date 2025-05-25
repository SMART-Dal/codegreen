mod intel_rapl;
mod arm_pmu;
mod nvidia_gpu;

use crate::{MeasurementSession, EnergyResult};
use hardware_plugins::{HardwarePlugin, Measurement};
use chrono::Duration;

/// Base adapter implementation that wraps a hardware plugin
pub struct BaseAdapter {
    name: &'static str,
    plugin: Box<dyn HardwarePlugin>,
}

impl BaseAdapter {
    pub fn new(name: &'static str, plugin: Box<dyn HardwarePlugin>) -> Self {
        Self { name, plugin }
    }

    /// Calculate the duration between two measurements
    pub fn calculate_duration(start: &Measurement, end: &Measurement) -> Duration {
        end.timestamp.signed_duration_since(start.timestamp)
    }

    /// Calculate the energy delta between two measurements
    pub fn calculate_energy_delta(start: &Measurement, end: &Measurement) -> f64 {
        end.joules - start.joules
    }

    /// Create a measurement session from start and end measurements
    pub fn create_session(
        start: Measurement,
        end: Measurement,
    ) -> MeasurementSession {
        let duration = Self::calculate_duration(&start, &end);
        let total_energy = Self::calculate_energy_delta(&start, &end);

        let mut start_measurements = std::collections::HashMap::new();
        let mut end_measurements = std::collections::HashMap::new();
        start_measurements.insert("base".to_string(), start.clone());
        end_measurements.insert("base".to_string(), end.clone());

        MeasurementSession {
            start_measurements,
            end_measurements,
            start: start.timestamp,
            end: end.timestamp,
            duration: duration.to_std().unwrap_or_default(),
            total_energy,
        }
    }

    /// Get the underlying plugin
    pub fn plugin(&self) -> &dyn HardwarePlugin {
        self.plugin.as_ref()
    }

    /// Get the adapter name
    pub fn name(&self) -> &str {
        self.name
    }
}

pub trait EnergyAdapter: Send + Sync {
    fn name(&self) -> &str;
    fn initialize(&mut self) -> EnergyResult<()>;
    fn shutdown(&mut self) -> EnergyResult<()>;
    fn read_measurements(&self) -> EnergyResult<Vec<Measurement>>;
}

pub use intel_rapl::IntelRaplAdapter;
pub use arm_pmu::ArmPmuAdapter;
pub use nvidia_gpu::NvidiaGpuAdapter; 