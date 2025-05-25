use crate::{EnergyMeasurement, EnergyResult, MeasurementSession};
use std::collections::HashMap;
use std::time::{Duration, Instant};

/// A measurement session that tracks multiple energy sources
pub struct MultiSourceSession {
    /// Start measurements for each source
    start_measurements: HashMap<String, EnergyMeasurement>,
    /// End measurements for each source
    end_measurements: HashMap<String, EnergyMeasurement>,
    /// Start time of the session
    start_time: Instant,
    /// End time of the session
    end_time: Option<Instant>,
}

impl MultiSourceSession {
    /// Create a new multi-source measurement session
    pub fn new() -> Self {
        Self {
            start_measurements: HashMap::new(),
            end_measurements: HashMap::new(),
            start_time: Instant::now(),
            end_time: None,
        }
    }

    /// Add a start measurement for a source
    pub fn add_start_measurement(&mut self, measurement: EnergyMeasurement) {
        self.start_measurements.insert(measurement.source.clone(), measurement);
    }

    /// Add an end measurement for a source
    pub fn add_end_measurement(&mut self, measurement: EnergyMeasurement) {
        self.end_measurements.insert(measurement.source.clone(), measurement);
    }

    /// End the session
    pub fn end(&mut self) {
        self.end_time = Some(Instant::now());
    }

    /// Get the duration of the session
    pub fn duration(&self) -> Option<Duration> {
        self.end_time.map(|end| end.duration_since(self.start_time))
    }

    /// Get the total energy consumption across all sources
    pub fn total_energy(&self) -> f64 {
        self.start_measurements
            .iter()
            .filter_map(|(source, start)| {
                self.end_measurements.get(source).map(|end| {
                    end.joules - start.joules
                })
            })
            .sum()
    }

    /// Get the average power consumption across all sources
    pub fn average_power(&self) -> Option<f64> {
        self.duration().map(|duration| {
            if duration.as_secs_f64() > 0.0 {
                self.total_energy() / duration.as_secs_f64()
            } else {
                0.0
            }
        })
    }

    /// Get individual measurement sessions for each source
    pub fn get_source_sessions(&self) -> Vec<MeasurementSession> {
        self.start_measurements
            .iter()
            .filter_map(|(source, start)| {
                self.end_measurements.get(source).map(|end| {
                    let duration = end.timestamp.duration_since(start.timestamp);
                    let total_energy = end.joules - start.joules;

                    MeasurementSession {
                        start: start.clone(),
                        end: end.clone(),
                        duration,
                        total_energy,
                    }
                })
            })
            .collect()
    }
} 