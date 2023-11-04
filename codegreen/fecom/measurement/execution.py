"""
Functions to run directly before and after a function call to measure energy consumption.
"""

import time
import pickle
import atexit
import json
import psutil
from pathlib import Path
from datetime import datetime
from pympler import asizeof
import sys
import tensorflow as tf

from codegreen.fecom.measurement.utilities import custom_print
from codegreen.fecom.measurement.start_measurement import start_sensors, quit_process, unregister_and_quit_process

from codegreen.fecom.measurement.stable_check import run_check_loop, machine_is_stable_check, temperature_is_low_check
from codegreen.fecom.measurement.measurement_parse import get_current_times, get_energy_data, get_cpu_temperature_data

from codegreen.fecom.measurement.measurement_config import DEBUG, SKIP_CALLS_FILE_NAME, MEASUREMENT_MODULE_NAME
# stable state constants
from codegreen.fecom.measurement.measurement_config import MAX_WAIT_S, WAIT_AFTER_RUN_S, CPU_STD_TO_MEAN, RAM_STD_TO_MEAN, GPU_STD_TO_MEAN, CPU_MAXIMUM_TEMPERATURE, GPU_MAXIMUM_TEMPERATURE
# stable state settings
from codegreen.fecom.measurement.measurement_config import WAIT_PER_STABLE_CHECK_LOOP_S, CHECK_LAST_N_POINTS, STABLE_CHECK_TOLERANCE, CPU_TEMPERATURE_INTERVAL_S, MEASUREMENT_INTERVAL_S
# file paths and separators
from codegreen.fecom.measurement.measurement_config import PERF_FILE, NVIDIA_SMI_FILE, EXECUTION_LOG_FILE, START_TIMES_FILE, CPU_TEMPERATURE_FILE

from codegreen.fecom.experiment.experiment_kinds import ExperimentKinds


def print_exec(message: str):
    custom_print("execution", message)

def get_size(obj):
        # Sys.getsizeof() just returns the size of the item itself, whereas asizeof() returns the size of the object plus every object it references. As a result, asizeof() can show the memory utilisation of an object more clearly.
        try:
            if isinstance(obj, tf.Tensor) and tf.executing_eagerly():
                print("++++++1++++++")
                print("1-size",float(obj.numpy().nbytes))
                return float(obj.numpy().nbytes)
            elif isinstance(obj, (dict, list, tuple)):
                print("++++++4++++++")
                print("4-size",sum(get_size(x) for x in obj))
                return sum(get_size(x) for x in obj)
            else :
                try:
                    print("++++++5++++++")
                    print("5-size",float(asizeof.asizeof(obj)))
                    return float(asizeof.asizeof(obj))
                except Exception as e:
                    print("++++++6++++++",e)
                    print("6-size",float(sys.getsizeof(obj)))
                    return float(sys.getsizeof(obj))
        except Exception as e:
            print_exec(f"get_size_error: \n {e} \n ")

def is_measurement_running():
    for process in psutil.process_iter(attrs=['name', 'cmdline']):
        # Checking if the process name is python or python3
        if 'codegreen' in process.info['name']:
            # Checking the command line arguments to see if the measurement module name is present
            if any(MEASUREMENT_MODULE_NAME in part for part in process.info['cmdline']):
                return True
    return False


def prepare_state():
    """
    Ensure the machine is in the right state before starting execution
    """
    # (0) check that the measurement script is running
    if not is_measurement_running():
        raise RuntimeError(f"Please start the measurement program before running experiments. If you are running the measurement program, please check that the module name ({MEASUREMENT_MODULE_NAME}) is correct in the measurement_config.py file.")

    # (1) start the cpu temperature measurement process
    sensors = start_sensors(print_exec)
    # give sensors some time to gather initial measurements
    time.sleep(3)
    atexit.register(quit_process, sensors, "sensors", print_exec)


    # (2) continue only when CPU & GPU temperatures are below threshold and the system has reached a stable state of energy consumption

    # (2a) check that temperatures are below threshold, then quit the CPU temperature measurement process
    begin_temperature_check_time = time.time_ns()
    if not run_check_loop(True, MAX_WAIT_S, WAIT_PER_STABLE_CHECK_LOOP_S, "low temperature", temperature_is_low_check, CHECK_LAST_N_POINTS, CPU_MAXIMUM_TEMPERATURE, GPU_MAXIMUM_TEMPERATURE):
        unregister_and_quit_process(sensors, "sensors")
        raise TimeoutError(f"CPU could not cool down to {CPU_MAXIMUM_TEMPERATURE} within {MAX_WAIT_S} seconds")
    unregister_and_quit_process(sensors, "sensors")

    # (2b) check that the CPU, RAM and GPU energy consumption is stable
    begin_stable_check_time = time.time_ns()
    if not run_check_loop(False, MAX_WAIT_S, WAIT_PER_STABLE_CHECK_LOOP_S, "stable state", machine_is_stable_check, CHECK_LAST_N_POINTS, STABLE_CHECK_TOLERANCE, CPU_STD_TO_MEAN, RAM_STD_TO_MEAN, GPU_STD_TO_MEAN):
        raise TimeoutError(f"Could not reach a stable state within {MAX_WAIT_S} seconds")

    # (3a) Get the start times from the files and also save their exact value.
    # TODO potentially correct here for the small time offset created by fetching the times from the files. We can use the execution times for this.
    start_time_perf, start_time_nvidia = get_current_times(PERF_FILE, NVIDIA_SMI_FILE)
    start_time_execution = time.time_ns()
    
    return start_time_perf, start_time_nvidia, start_time_execution, begin_stable_check_time, begin_temperature_check_time


def load_skip_calls(skip_calls_file_path: Path):
    """
    Get the list of calls to skip from the file.
    """
    if skip_calls_file_path.is_file():
        with open(skip_calls_file_path, 'r') as f:
            skip_calls = json.load(f)
    else:
        skip_calls = []
    return skip_calls


def should_skip_call(experiment_file_path: str, function_to_run: str = None):
    assert experiment_file_path is not None, "If experiment_file_path is None, skip calls should not be enabled."

    skip_calls = load_skip_calls(experiment_file_path.parent / SKIP_CALLS_FILE_NAME)
    
    if function_to_run in skip_calls:
        return True


def store_data(data: dict, experiment_file_path: Path):
    """
    Create a new file and store the data as json, or append it to the existing data in this file.
    """
    
    if DEBUG:
        print_exec(f"Result: {str(data)[:100]}")

    # Create parent directories if they don't exist
    experiment_file_path.parent.mkdir(parents=True, exist_ok=True)

    if experiment_file_path.is_file():
        with open(experiment_file_path, 'r') as f:
            file_content = f.read()
        if file_content.strip():
            existing_data = json.loads(file_content)
        else:
            existing_data = []
    else:
        existing_data = []

    existing_data.append(data)
    with open(experiment_file_path, 'w') as f:
        json.dump(existing_data, f)
    if DEBUG:
        print_exec(f"Data written to file {str(experiment_file_path)}")


"""
Core functions
"""

def before_execution(experiment_file_path: str, function_to_run: str = None, enable_skip_calls: bool = True):
    """
    Insert directly before the function call in the script.
    If enable_skip_calls is False, then no skipped_calls file will be checked. This is useful for
    - project-level experiments
    - data-size experiments
    """
    # check if we should skip this call (e.g. if it doesn't consume energy)
    if enable_skip_calls and function_to_run and should_skip_call(experiment_file_path, function_to_run):
        return

    # re-try finding stable state in a loop
    while True:
        try:
            print_exec("Waiting before running function for 10 seconds.")
            time.sleep(10)
            start_time_perf, start_time_nvidia, start_time_execution, begin_stable_check_time, begin_temperature_check_time = prepare_state()
            print_exec("Successfully reached stable state")
            break
        except TimeoutError as e:
            error_file = "timeout_energy_data.json"
            with open(error_file, 'w') as f:
                json.dump(get_energy_data(PERF_FILE, NVIDIA_SMI_FILE)[0], f)
            time.sleep(30)
            continue  # retry reaching stable state
    
    start_times = {
        "start_time_perf": start_time_perf,
        "start_time_nvidia": start_time_nvidia,
        "start_time_execution": start_time_execution,
        "begin_stable_check_time": begin_stable_check_time,
        "begin_temperature_check_time": begin_temperature_check_time

    }
    return start_times


def after_execution(
        start_times: dict, experiment_file_path: str, function_to_run: str = None,project_metadata: dict = None,
        method_object: str = None, function_args: list = None, function_kwargs: dict = None,
        enable_skip_calls: bool = True):
    """
    Insert directly after the function call in the script.

    For project-level experiments, function_to_run is None. The patcher should then
    simply prepend the before_execution call to the file, and append the after_execution
    call after the last line.

    The start_times are provided by the return of before_execution, the rest
    by the patcher.
    """
    # check if we should skip this call (e.g. if it doesn't consume energy)
    if enable_skip_calls and function_to_run and should_skip_call(experiment_file_path, function_to_run):
        return
    
    # (3b) Get the end times from the files and also save their exact value.
    end_time_execution = time.time_ns()
    end_time_perf, end_time_nvidia = get_current_times(PERF_FILE, NVIDIA_SMI_FILE)

    # (4) Wait some specified amount of time to measure potentially elevated energy consumption after the function has terminated
    if DEBUG:
        print_exec(f"waiting idle for {WAIT_AFTER_RUN_S} seconds after function execution")
    if WAIT_AFTER_RUN_S > 0:
        time.sleep(WAIT_AFTER_RUN_S)
    
    # if this is a project-level experiment, function_to_run is None so set it to project-level
    if function_to_run is None:
        function_to_run = ExperimentKinds.PROJECT_LEVEL.value
    
    if DEBUG:
        print_exec(f"Performed {function_to_run[:100]} on input and will now save energy data.")

    # (5) get the energy data & gather all start and end times
    energy_data, df_gpu = get_energy_data(PERF_FILE, NVIDIA_SMI_FILE)
    cpu_temperatures = get_cpu_temperature_data(CPU_TEMPERATURE_FILE)

    # "normalise" nvidia-smi start/end times such that the first value in the gpu energy data has timestamp 0
    start_time_nvidia_normalised = start_times["start_time_nvidia"] - df_gpu["timestamp"].iloc[0]
    end_time_nvidia_normalised = end_time_nvidia - df_gpu["timestamp"].iloc[0]

    # get the start times generated by start_measurement.py
    with open(START_TIMES_FILE, 'r') as f:
        raw_times = f.readlines()
    
    # START_TIMES_FILE has format PERF_START <time_perf>\nNVIDIA_SMI_START <time_nvidia>
    sys_start_time_perf, sys_start_time_nvidia = [int(line.strip(' \n').split(" ")[1]) for line in raw_times]

    times = {
        "start_time_execution": start_times["start_time_execution"],
        "end_time_execution": end_time_execution,
        "start_time_perf": start_times["start_time_perf"], 
        "end_time_perf": end_time_perf,
        "sys_start_time_perf": sys_start_time_perf,
        "start_time_nvidia": start_time_nvidia_normalised,
        "end_time_nvidia": end_time_nvidia_normalised,
        "sys_start_time_nvidia": sys_start_time_nvidia,
        "begin_stable_check_time": start_times["begin_stable_check_time"],
        "begin_temperature_check_time": start_times["begin_temperature_check_time"]
    }

    # (6) if the runtime is below 0.5s, there is no energy data for this method so add it to the skip_calls list
    if enable_skip_calls:
        skip_calls_file_path = experiment_file_path.parent / SKIP_CALLS_FILE_NAME
        skip_calls = load_skip_calls(skip_calls_file_path)

        if(start_time_nvidia_normalised == end_time_nvidia_normalised or start_times["start_time_perf"] == end_time_perf):
            if function_to_run not in skip_calls:
                skip_calls.append(function_to_run)
                with open(skip_calls_file_path, 'w') as f:
                    json.dump(skip_calls, f)
                print_exec('skipping call added, current list is: '+ str(skip_calls))
            else:
                print_exec('Skipping call already exists.')

    # (7) collect all relevant settings
    settings = {
        "max_wait_s": MAX_WAIT_S,
        "wait_after_run_s": WAIT_AFTER_RUN_S,
        "wait_per_stable_check_loop_s": WAIT_PER_STABLE_CHECK_LOOP_S,
        "tolerance": STABLE_CHECK_TOLERANCE,
        "measurement_interval_s": MEASUREMENT_INTERVAL_S,
        "cpu_std_to_mean": CPU_STD_TO_MEAN,
        "ram_std_to_mean": RAM_STD_TO_MEAN,
        "gpu_std_to_mean": GPU_STD_TO_MEAN,
        "check_last_n_points": CHECK_LAST_N_POINTS,
        "cpu_max_temp": CPU_MAXIMUM_TEMPERATURE,
        "gpu_max_temp": GPU_MAXIMUM_TEMPERATURE,
        "cpu_temperature_interval_s": CPU_TEMPERATURE_INTERVAL_S
    }

    # (8) Add size data using pickle, if possible
    # some objects cannot be pickled, so catch any exceptions and set the size to None for those objects
    try:
        # args_size = len(pickle.dumps(function_args)) if function_args is not None else None
        print("inside_arg_size")
        args_size = get_size(function_args) if function_args is not None else 0
        print("outside_arg_size")
    except Exception as e:
        print_exec(f"Could not pickle function args. Error: \n {e} \n Args Size will be None for this function. Execution will continue normally.")
        args_size = None
    try:
        # kwargs_size = len(pickle.dumps(function_kwargs)) if function_kwargs is not None else None
        print("inside_kwarg_size")
        kwargs_size = get_size(function_kwargs) if function_kwargs is not None else 0
        print("outside_kwarg_size")
    except Exception as e:
        print_exec(f"Could not pickle function kwargs. Error: \n {e} \n Kwargs Size will be None for this function. Execution will continue normally.")
        kwargs_size = None
    try:
        # object_size = len(pickle.dumps(method_object)) if method_object is not None else None
        print("inside_object_size")
        object_size = get_size(method_object) if method_object is not None else 0
        print("outside_object_size")
    except Exception as e:
        print_exec(f"Could not pickle method object. Error: \n {e} \n Object Size will be None for this function. Execution will continue normally.")
        object_size = None

    input_sizes = {
        "args_size": args_size,
        "kwargs_size": kwargs_size,
        "object_size": object_size
    }

    # (9) format the return dictionary to be in the format {function_signature: results}
    results = {
        function_to_run: {
            "energy_data": energy_data,
            "times": times,
            "cpu_temperatures": cpu_temperatures,
            "settings": settings,
            "input_sizes": input_sizes,
            "project_metadata": project_metadata
        }
    }
        
    # (10) Write the method details to the execution log file with a time stamp (to keep entries unique)
    # This triggers the reload of perf & nvidia-smi, clearing the energy data from the execution of this function
    # (see fecom.measurement.start_measurement for the implementation of this process) 
    with open(EXECUTION_LOG_FILE, 'a') as f:
        f.write(f"{function_to_run};{datetime.now().strftime('%H:%M:%S')}\n")

    store_data(results, experiment_file_path)