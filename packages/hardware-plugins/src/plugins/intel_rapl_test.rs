#[cfg(test)]
mod tests {
    use super::*;
    use mockall::predicate::*;
    use mockall::mock;
    use std::fs::File;
    use std::io::Write;
    use tempfile::tempdir;

    mock! {
        File {
            fn read_exact(&mut self, buf: &mut [u8]) -> std::io::Result<()>;
        }
    }

    #[test]
    fn test_rapl_plugin_initialization() {
        let mut plugin = IntelRAPLPlugin::new();
        assert_eq!(plugin.name(), "intel_rapl");
        assert!(plugin.description().contains("Intel RAPL"));
    }

    #[test]
    fn test_rapl_plugin_availability() {
        let plugin = IntelRAPLPlugin::new();
        // This test will be skipped if MSR is not available
        if !plugin.is_available() {
            println!("Skipping RAPL availability test - MSR not available");
            return;
        }
        assert!(plugin.is_available());
    }

    #[test]
    fn test_rapl_measurement_flow() {
        let mut plugin = IntelRAPLPlugin::new();
        if !plugin.is_available() {
            println!("Skipping RAPL measurement test - MSR not available");
            return;
        }

        // Test measurement lifecycle
        assert!(plugin.initialize().is_ok());
        assert!(plugin.start_measurement().is_ok());
        assert!(plugin.get_measurement().is_ok());
        assert!(plugin.stop_measurement().is_ok());
    }

    #[test]
    fn test_rapl_supported_metrics() {
        let plugin = IntelRAPLPlugin::new();
        let metrics = plugin.supported_metrics();
        assert!(metrics.contains(&"power_watts"));
        assert!(metrics.contains(&"dram_energy_joules"));
    }

    #[test]
    fn test_rapl_measurement_validation() {
        let mut plugin = IntelRAPLPlugin::new();
        if !plugin.is_available() {
            println!("Skipping RAPL validation test - MSR not available");
            return;
        }

        // Test double start
        assert!(plugin.start_measurement().is_ok());
        assert!(plugin.start_measurement().is_err());

        // Test stop without start
        assert!(plugin.stop_measurement().is_ok());
        assert!(plugin.stop_measurement().is_err());
    }
} 