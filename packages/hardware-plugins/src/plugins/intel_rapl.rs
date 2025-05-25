use std::fs;
use std::path::Path;
use std::time::Instant;
use super::{HardwarePlugin, HardwareError, Measurement};

const MSR_POWER_UNIT: u32 = 0x606;
const MSR_PKG_ENERGY_STATUS: u32 = 0x611;
const MSR_DRAM_ENERGY_STATUS: u32 = 0x619;

pub struct IntelRAPLPlugin {
    msr_path: String,
    power_units: f64,
    energy_units: f64,
    time_units: f64,
    last_measurement: Option<Measurement>,
    measurement_start: Option<Instant>,
}

impl IntelRAPLPlugin {
    pub fn new() -> Self {
        Self {
            msr_path: String::from("/dev/cpu/0/msr"),
            power_units: 0.0,
            energy_units: 0.0,
            time_units: 0.0,
            last_measurement: None,
            measurement_start: None,
        }
    }

    fn read_msr(&self, msr: u32) -> Result<u64, HardwareError> {
        let path = Path::new(&self.msr_path);
        if !path.exists() {
            return Err(HardwareError::DeviceNotFound(
                "MSR device not found. Make sure msr module is loaded.".to_string(),
            ));
        }

        let mut file = fs::File::open(path)
            .map_err(|e| HardwareError::PermissionDenied(format!("Failed to open MSR: {}", e)))?;

        let mut buffer = [0u8; 8];
        file.read_exact(&mut buffer)
            .map_err(|e| HardwareError::SensorError(format!("Failed to read MSR: {}", e)))?;

        Ok(u64::from_le_bytes(buffer))
    }

    fn read_power_unit(&mut self) -> Result<(), HardwareError> {
        let power_unit = self.read_msr(MSR_POWER_UNIT)?;
        
        // Extract power, energy, and time units from the MSR
        self.power_units = 1.0 / (1u64 << ((power_unit >> 0) & 0xF)) as f64;
        self.energy_units = 1.0 / (1u64 << ((power_unit >> 8) & 0x1F)) as f64;
        self.time_units = 1.0 / (1u64 << ((power_unit >> 16) & 0xF)) as f64;
        
        Ok(())
    }
}

impl HardwarePlugin for IntelRAPLPlugin {
    fn initialize(&mut self) -> Result<(), HardwareError> {
        self.read_power_unit()?;
        Ok(())
    }

    fn name(&self) -> &'static str {
        "intel_rapl"
    }

    fn description(&self) -> &'static str {
        "Intel RAPL (Running Average Power Limit) energy measurement plugin"
    }

    fn is_available(&self) -> bool {
        Path::new(&self.msr_path).exists()
    }

    fn start_measurement(&mut self) -> Result<(), HardwareError> {
        if self.measurement_start.is_some() {
            return Err(HardwareError::UnsupportedOperation(
                "Measurement already in progress".to_string(),
            ));
        }
        self.measurement_start = Some(Instant::now());
        Ok(())
    }

    fn stop_measurement(&mut self) -> Result<(), HardwareError> {
        if self.measurement_start.is_none() {
            return Err(HardwareError::UnsupportedOperation(
                "No measurement in progress".to_string(),
            ));
        }
        self.measurement_start = None;
        Ok(())
    }

    fn get_measurement(&self) -> Result<Measurement, HardwareError> {
        let pkg_energy = self.read_msr(MSR_PKG_ENERGY_STATUS)?;
        let dram_energy = self.read_msr(MSR_DRAM_ENERGY_STATUS)?;

        let mut additional_metrics = std::collections::HashMap::new();
        additional_metrics.insert("dram_energy_joules".to_string(), dram_energy as f64 * self.energy_units);

        let measurement = Measurement {
            timestamp: Instant::now(),
            power_watts: pkg_energy as f64 * self.power_units,
            temperature_celsius: None, // RAPL doesn't provide temperature
            additional_metrics,
        };

        Ok(measurement)
    }

    fn supported_metrics(&self) -> Vec<&'static str> {
        vec!["power_watts", "dram_energy_joules"]
    }
} 