use energy_core::{
    MeasurementSession, MultiSourceSession,
    EnergyResult, EnergyError,
};
use std::time::{Duration, Instant};

#[test]
fn test_energy_measurement_creation() {
    let now = Instant::now();
    let measurement = Measurement {
        timestamp: now,
        joules: 100.0,
        watts: 50.0,
        source: "test".to_string(),
    };

    assert_eq!(measurement.joules, 100.0);
    assert_eq!(measurement.watts, 50.0);
    assert_eq!(measurement.source, "test");
}

#[test]
fn test_measurement_session_creation() {
    let start = Measurement {
        timestamp: Instant::now(),
        joules: 100.0,
        watts: 50.0,
        source: "test".to_string(),
    };

    let end = Measurement {
        timestamp: start.timestamp + Duration::from_secs(1),
        joules: 150.0,
        watts: 50.0,
        source: "test".to_string(),
    };

    let session = MeasurementSession {
        start: start.clone(),
        end: end.clone(),
        duration: Duration::from_secs(1),
        total_energy: 50.0,
    };

    assert_eq!(session.duration.as_secs(), 1);
    assert_eq!(session.total_energy, 50.0);
    assert_eq!(session.start.joules, 100.0);
    assert_eq!(session.end.joules, 150.0);
}

#[test]
fn test_multi_source_session() {
    let mut session = MultiSourceSession::new();
    
    // Add start measurements
    let start1 = Measurement {
        timestamp: Instant::now(),
        joules: 100.0,
        watts: 50.0,
        source: "source1".to_string(),
    };
    let start2 = Measurement {
        timestamp: start1.timestamp,
        joules: 200.0,
        watts: 100.0,
        source: "source2".to_string(),
    };
    session.add_start_measurement(start1);
    session.add_start_measurement(start2);

    // Add end measurements
    let end1 = Measurement {
        timestamp: start1.timestamp + Duration::from_secs(1),
        joules: 150.0,
        watts: 50.0,
        source: "source1".to_string(),
    };
    let end2 = Measurement {
        timestamp: start2.timestamp + Duration::from_secs(1),
        joules: 300.0,
        watts: 100.0,
        source: "source2".to_string(),
    };
    session.add_end_measurement(end1);
    session.add_end_measurement(end2);

    session.end();

    // Verify results
    assert_eq!(session.total_energy(), 150.0); // (150-100) + (300-200)
    assert!(session.average_power().unwrap() > 0.0);
    
    let source_sessions = session.get_source_sessions();
    assert_eq!(source_sessions.len(), 2);
    assert_eq!(source_sessions[0].total_energy, 50.0);
    assert_eq!(source_sessions[1].total_energy, 100.0);
}

#[test]
fn test_energy_error_creation() {
    let error = EnergyError::HardwareNotSupported("test".to_string());
    assert!(error.to_string().contains("test"));

    let error = EnergyError::MeasurementFailed("test".to_string());
    assert!(error.to_string().contains("test"));

    let error = EnergyError::PluginError("test".to_string());
    assert!(error.to_string().contains("test"));

    let error = EnergyError::LanguageAdapterError("test".to_string());
    assert!(error.to_string().contains("test"));
}

#[test]
fn test_measurement_validation() {
    let start = Measurement {
        timestamp: Instant::now(),
        joules: 100.0,
        watts: 50.0,
        source: "test".to_string(),
    };

    let end = Measurement {
        timestamp: start.timestamp - Duration::from_secs(1), // Invalid: end before start
        joules: 50.0, // Invalid: less energy than start
        watts: 50.0,
        source: "test".to_string(),
    };

    let session = MeasurementSession {
        start: start.clone(),
        end: end.clone(),
        duration: Duration::from_secs(1),
        total_energy: -50.0, // Invalid: negative energy
    };

    // These assertions should fail, indicating invalid measurements
    assert!(session.duration.as_secs() > 0, "Invalid duration");
    assert!(session.total_energy >= 0.0, "Negative energy consumption");
    assert!(session.end.joules >= session.start.joules, "End energy less than start energy");
} 