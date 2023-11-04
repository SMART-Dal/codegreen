from pathlib import Path
from codegreen.fecom.patching.patching_config import PROJECT_PATH, TOOL_INSTALLATION_PATH

# set this to False to surpress some print outs
DEBUG = True

"""
STABLE STATE CONFIG
"""
# seconds to wait after function execution
WAIT_AFTER_RUN_S = 30

# maximum time (seconds) to wait for the machine to reach a stable state
MAX_WAIT_S = 120

# re-calculate statistics every x seconds when checking stable state
WAIT_PER_STABLE_CHECK_LOOP_S = 20

# only consider the last n points, with perf stat/nvidia-smi interval of 0.5secs this corresponds to the last 10 seconds
CHECK_LAST_N_POINTS = 20

# relative tolerance for difference between stable stdev/mean ratio and current ratios as measured by the stable checking mechanism
# e.g. 0.1 would mean allowing a ratio that's 10% higher than the stable stdev/mean ratio
STABLE_CHECK_TOLERANCE = 0

# average (mean) standard deviations and means for stable energy data for 20 values in a row from, generated with replication/settings_calculation.stdev_mean_ratios()
# Do not change these between experiments!
CPU_STD_TO_MEAN = 0.03
RAM_STD_TO_MEAN = 0.03
GPU_STD_TO_MEAN = 0.01

# used by fecom.experiment.analysis
STABLE_CPU_ENERGY_STDEV = 0.402764
STABLE_CPU_ENERGY_MEAN = 17.049285
STABLE_RAM_ENERGY_STDEV = 0.083274
STABLE_RAM_ENERGY_MEAN = 3.547466
STABLE_GPU_POWER_STDEV = 0.114850
STABLE_GPU_POWER_MEAN = 18.517920

"""
ENERGY MEASUREMENT CONFIG
"""
# MEASUREMENT_MODULE_NAME = "start_measurement.py"
MEASUREMENT_MODULE_NAME = "run-energy-profiler"
# this is also used for the cpu temperature file
CPU_FILE_SEPARATOR = ';'
# set measurement interval for perf & nvidia-smi in milliseconds
MEASUREMENT_INTERVAL_MS = 500
# having the measurement interval in seconds is useful for converting power to energy and vice versa
MEASUREMENT_INTERVAL_S = MEASUREMENT_INTERVAL_MS / 1000
# path to find energy data relative to the measurement package
ENERGY_DATA_DIR = TOOL_INSTALLATION_PATH / "measurement/out"
# store perf & nvidia-smi output here
PERF_FILE = ENERGY_DATA_DIR/"perf.txt"
NVIDIA_SMI_FILE = ENERGY_DATA_DIR/"nvidia_smi.txt"
# store start times here
START_TIMES_FILE = ENERGY_DATA_DIR/"start_times.txt"
# keep track of executed functions in this file
EXECUTION_LOG_FILE = ENERGY_DATA_DIR/"execution_log.txt"

# seconds to wait until printing stability stats after starting energy measurement processes
WAIT_UNTIL_PRINTING_STATS_S = 120


SKIP_CALLS_FILE_NAME = "skip_calls.json"


"""
TEMPERATURE MEASUREMENT CONFIG
"""
CPU_TEMPERATURE_MODULE = TOOL_INSTALLATION_PATH / "measurement/cpu_temperature.py"
# set cpu temperature measurement interval for sensors in seconds
# the actual interval will be a few milliseconds greater, due to processing time
CPU_TEMPERATURE_INTERVAL_S = 1
# store CPU temperatures in this file, populated by cpu_temperature.py
CPU_TEMPERATURE_FILE = ENERGY_DATA_DIR/"cpu_temperature.txt"
# the maximum average temperature in degrees Celsius that we allow the CPU & GPU to be before executing a method (to determine stable state)
CPU_MAXIMUM_TEMPERATURE = 55 # see replication package for how we arrived at this value
GPU_MAXIMUM_TEMPERATURE = 40