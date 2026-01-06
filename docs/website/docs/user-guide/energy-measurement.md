# Energy Measurement

CodeGreen uses the Native Energy Measurement Backend (NEMB) to provide high-precision energy monitoring with minimal overhead.

## Supported Hardware Sensors

CodeGreen supports a wide range of hardware sensors through its extensible driver architecture:

| Sensor Type | Driver Name | Implementation | Platforms |
|-------------|-------------|----------------|-----------|
| **CPU (Intel)** | Intel RAPL | `intel_rapl_provider.cpp` | Linux |
| **GPU (NVIDIA)** | NVIDIA NVML | `nvidia_gpu_provider.cpp` | Linux, Windows |
| **GPU (AMD)** | AMD GPU (via ROCm SMI) | `amd_gpu_provider.cpp` | Linux |
| **System** | PowerSensor | `powersensor_provider.cpp` | Linux |

## Measurement Methodology

### Background Polling
NEMB runs a dedicated high-priority C++ thread that samples hardware sensors at a configurable interval (default: 1ms). This ensures that energy consumption is captured even for very short-lived code segments.

### Signal-Generator Model
Instead of performing slow, synchronous hardware reads at every checkpoint, CodeGreen inserts lightweight "signals" (timestamps) into the code. These signals take approximately 100-200ns to record, compared to 5-20μs for a direct hardware read.

### Correlation and Interpolation
After the workload completes, CodeGreen correlates the timestamps from the signals with the time-series energy data collected by the background thread. Linear interpolation is used to estimate energy consumption between samples with high precision.

## Precision and Accuracy

| Metric | Value |
|--------|-------|
| **Measurement Overhead** | < 0.1% |
| **Polling Resolution** | 1ms |
| **Accuracy** | ±2% (Hardware dependent) |

## Performance Considerations
For most applications, the default polling interval of 1ms provides an ideal balance between resolution and overhead. If you are measuring extremely long-running workloads (minutes or hours), you may consider increasing the polling interval to 10ms or 100ms via `codegreen.json`.