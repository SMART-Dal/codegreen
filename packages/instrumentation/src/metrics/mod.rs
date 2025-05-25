use crate::error::InstrumentationError;
use influxdb::{Client, WriteQuery, ReadQuery, Timestamp};
use prometheus::{Registry, Gauge, Counter};
use std::sync::{Arc, Mutex};
use hardware_plugins::Measurement;

pub struct MetricsStore {
    prometheus: Arc<Mutex<Registry>>,
    client: Client,
    energy_gauge: Gauge,
    total_energy_counter: Counter,
}

impl MetricsStore {
    pub fn new(url: &str, database: &str) -> Result<Self, InstrumentationError> {
        let registry = Registry::new();
        let energy_gauge = Gauge::new("energy_consumption_joules", "Current energy consumption in joules")
            .map_err(|e| InstrumentationError::MeasurementError(e.to_string()))?;
        let total_energy_counter = Counter::new("total_energy_joules", "Total energy consumed in joules")
            .map_err(|e| InstrumentationError::MeasurementError(e.to_string()))?;

        registry.register(Box::new(energy_gauge.clone()))
            .map_err(|e| InstrumentationError::MeasurementError(e.to_string()))?;
        registry.register(Box::new(total_energy_counter.clone()))
            .map_err(|e| InstrumentationError::MeasurementError(e.to_string()))?;

        let client = Client::new(url, database);

        Ok(Self {
            prometheus: Arc::new(Mutex::new(registry)),
            client,
            energy_gauge,
            total_energy_counter,
        })
    }

    pub async fn record_measurement(&self, measurement: &Measurement) -> Result<(), InstrumentationError> {
        // Update Prometheus metrics
        self.energy_gauge.set(measurement.joules);
        self.total_energy_counter.inc_by(measurement.joules);

        // Store in InfluxDB
        let millis = measurement.timestamp.timestamp_millis();
        let millis_u128 = if millis < 0 {
            0 // Handle negative timestamps by using 0
        } else {
            millis as u128
        };

        let query = WriteQuery::new(
            Timestamp::Milliseconds(millis_u128),
            "energy_measurements"
        )
        .add_field("joules", measurement.joules);

        self.client.query(&query).await?;
        Ok(())
    }

    pub async fn get_measurements(&self, start: chrono::DateTime<chrono::Utc>, end: chrono::DateTime<chrono::Utc>) -> Result<Vec<Measurement>, InstrumentationError> {
        let query = ReadQuery::new(
            format!(
                "SELECT joules FROM energy_measurements WHERE time >= '{}' AND time <= '{}'",
                start.to_rfc3339(),
                end.to_rfc3339()
            )
        );

        let result = self.client.query(&query).await?;
        self.parse_measurements(result)
    }

    fn parse_measurements(&self, _result: String) -> Result<Vec<Measurement>, InstrumentationError> {
        // TODO: Implement parsing of InfluxDB response
        Ok(Vec::new())
    }
} 