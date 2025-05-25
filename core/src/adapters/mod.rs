mod intel_rapl;
mod nvidia_gpu;
mod arm_pmu;

pub use intel_rapl::IntelRAPLAdapter;
pub use nvidia_gpu::NvidiaGPUAdapter;
pub use arm_pmu::ArmPMUAdapter;

use crate::{EnergyAdapter, EnergyMeasurement, EnergyResult, MeasurementSession};
use async_trait::async_trait;
use std::sync::Arc;

/// Base adapter implementation that wraps a hardware plugin
pub struct BaseAdapter {
    name: &'static str,
    plugin: Arc<dyn HardwarePlugin>,
}

impl BaseAdapter {
    pub fn new(name: &'static str, plugin: Arc<dyn HardwarePlugin>) -> Self {
        Self { name, plugin }
    }

    /// Calculate the duration between two measurements
    pub fn calculate_duration(start: &EnergyMeasurement, end: &EnergyMeasurement) -> std::time::Duration {
        end.timestamp.duration_since(start.timestamp)
    }

    /// Calculate the energy delta between two measurements
    pub fn calculate_energy_delta(start: &EnergyMeasurement, end: &EnergyMeasurement) -> f64 {
        end.joules - start.joules
    }

    /// Create a measurement session from start and end measurements
    pub fn create_session(
        start: EnergyMeasurement,
        end: EnergyMeasurement,
    ) -> MeasurementSession {
        let duration = Self::calculate_duration(&start, &end);
        let total_energy = Self::calculate_energy_delta(&start, &end);

        MeasurementSession {
            start,
            end,
            duration,
            total_energy,
        }
    }
} 