// src/networkquality_bridge/src/lib.rs
use pyo3::prelude::*;
use pyo3::types::PyDict;
use tokio::runtime::Runtime;
// Use the higher-level 'networkquality' crate
use networkquality::{
    Client,
    Config as NqConfig, // Alias for networkquality::Config
    DownloadConfig as NqDownloadConfig, // Alias for networkquality::DownloadConfig
    UploadConfig as NqUploadConfig,     // Alias for networkquality::UploadConfig
    Measurement,                        // This is networkquality::model::Measurement
};
use std::sync::Arc; // Required by networkquality::Client::new() if it needs Arc<Time/Network>
use std::time::Duration;
// For default Time and Network implementations if needed by Client::new() or Config
// Check if networkquality::Client::new() needs these or if it uses its own defaults.
// Based on networkquality/src/client.rs, Client::new() is parameterless and sets up its own.

#[pyclass]
#[derive(Clone)]
struct MeasurementResult {
    #[pyo3(get)]
    timestamp: f64,
    #[pyo3(get)]
    rpm_download: f64,
    #[pyo3(get)]
    rpm_upload: f64,
    #[pyo3(get)]
    base_rtt_ms: f64,
    #[pyo3(get)]
    loaded_rtt_download_ms: f64,
    #[pyo3(get)]
    loaded_rtt_upload_ms: f64,
    #[pyo3(get)]
    download_throughput_mbps: f64,
    #[pyo3(get)]
    upload_throughput_mbps: f64,
    #[pyo3(get)]
    download_responsiveness: f64,
    #[pyo3(get)]
    upload_responsiveness: f64,
}

#[pyclass]
struct NetworkQualityClient {
    runtime: Runtime,
    client: Client, // This is networkquality::Client
    default_server_url: String,
}

#[pymethods]
impl NetworkQualityClient {
    #[new]
    fn new(server_url: Option<String>) -> PyResult<Self> {
        let runtime = Runtime::new()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to create Tokio runtime: {}", e)
            ))?;

        let default_server_url = server_url.unwrap_or_else(|| "http://localhost:9090".to_string());
        // networkquality::Client::new() is parameterless
        let client = Client::new();

        Ok(NetworkQualityClient {
            runtime,
            client,
            default_server_url,
        })
    }

    fn measure(&self, _py: Python<'_>, target: Option<&str>, config_dict: Option<&Bound<'_, PyDict>>) -> PyResult<MeasurementResult> {
        let current_server_url = target.unwrap_or(&self.default_server_url).to_string();

        let duration_secs = config_dict
            .and_then(|c| c.get_item("duration").ok().flatten())
            .and_then(|d| d.extract::<u64>().ok())
            .unwrap_or(20);

        let parallel_streams_download = config_dict
            .and_then(|c| c.get_item("parallel_streams_download").ok().flatten()) // Specific key for download
            .and_then(|p| p.extract::<usize>().ok())
            .unwrap_or(16); // Default from your plan

        let parallel_streams_upload = config_dict
            .and_then(|c| c.get_item("parallel_streams_upload").ok().flatten()) // Specific key for upload
            .and_then(|p| p.extract::<usize>().ok())
            .unwrap_or(16); // Default from your plan


        // Construct the networkquality::Config
        let mut nq_config = NqConfig::default(); // Uses networkquality::Config
        nq_config.server_address = current_server_url;
        nq_config.duration = Duration::from_secs(duration_secs);

        // Configure download specific settings
        let mut download_config = NqDownloadConfig::default();
        download_config.parallel_streams = parallel_streams_download;
        // Add other download params if needed, e.g., enabled, test_size_bytes
        // download_config.enabled = true; // Assuming enabled by default or Python controls this
        nq_config.download = download_config;

        // Configure upload specific settings
        let mut upload_config = NqUploadConfig::default();
        upload_config.parallel_streams = parallel_streams_upload;
        // Add other upload params if needed
        // upload_config.enabled = true; // Assuming enabled by default or Python controls this
        nq_config.upload = upload_config;

        // Enable RPM tests (usually default, but good to be explicit if there are flags)
        // nq_config.rpm_tests_enabled = true; // Check networkquality::Config for such flags

        let measurement_future = self.client.measure(Some(nq_config));

        let result: Measurement = self.runtime.block_on(measurement_future)
            .map_err(|e| {
                let error_message = format!("Measurement failed: {:?}", e); // Error type from measure might be more specific
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(error_message)
            })?;

        Ok(MeasurementResult {
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs_f64(),
            rpm_download: result.download_rpm as f64,
            rpm_upload: result.upload_rpm as f64,
            base_rtt_ms: result.base_rtt.as_secs_f64() * 1000.0,
            loaded_rtt_download_ms: result.download_rtt.as_secs_f64() * 1000.0,
            loaded_rtt_upload_ms: result.upload_rtt.as_secs_f64() * 1000.0,
            download_throughput_mbps: result.download_throughput_mbps,
            upload_throughput_mbps: result.upload_throughput_mbps,
            download_responsiveness: result.download_responsiveness.unwrap_or(0.0),
            upload_responsiveness: result.upload_responsiveness.unwrap_or(0.0),
        })
    }

    fn measure_detailed(&self, py: Python<'_>, target: Option<&str>, config: Option<&Bound<'_, PyDict>>)
        -> PyResult<(MeasurementResult, Vec<f64>, Vec<f64>)> {
        let measurement_result = self.measure(py, target, config)?;

        // The networkquality::model::Measurement struct does not directly expose raw RTT samples.
        // The underlying nq_rpm::ResponsivenessResult has TimeSeries for latencies,
        // but these are not directly surfaced in the top-level Measurement.
        // If detailed RTT samples are crucial, we might need to:
        // 1. Modify the `networkquality` crate to expose them from `Measurement`.
        // 2. Or, revert to using `nq-rpm` directly and reconstruct the high-level metrics (more complex).
        // For now, returning empty vectors as per the original plan's structure.
        let rtt_samples_down: Vec<f64> = vec![];
        let rtt_samples_up: Vec<f64> = vec![];

        Ok((measurement_result, rtt_samples_down, rtt_samples_up))
    }
}

#[pymodule]
fn networkquality_rs(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NetworkQualityClient>()?;
    m.add_class::<MeasurementResult>()?;
    Ok(())
}
