use crate::adapters::EnergyAdapter;
use crate::EnergyResult;
use hardware_plugins::{HardwarePlugin, Measurement};

pub struct NvidiaGpuAdapter {
    base: super::BaseAdapter,
}

impl NvidiaGpuAdapter {
    pub fn new(plugin: Box<dyn HardwarePlugin>) -> Self {
        Self {
            base: super::BaseAdapter::new("nvidia_gpu", plugin),
        }
    }
}

impl EnergyAdapter for NvidiaGpuAdapter {
    fn name(&self) -> &str {
        self.base.name()
    }

    fn initialize(&mut self) -> EnergyResult<()> {
        Ok(())
    }

    fn shutdown(&mut self) -> EnergyResult<()> {
        Ok(())
    }

    fn read_measurements(&self) -> EnergyResult<Vec<Measurement>> {
        let measurement = self.base.plugin().get_measurement()?;
        Ok(vec![measurement])
    }
} 