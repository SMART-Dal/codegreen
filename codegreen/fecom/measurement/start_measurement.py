"""
Start the energy measurement scripts by running this python module.

It is useful for gathering precise start/end times of perf
& nvidia-smi, which helps to synchronise time measurements with
the execution script.
"""

from subprocess import Popen
from pathlib import Path
import shlex
import atexit
import time
import os
import sys

from codegreen.fecom.measurement.idle_stats import calc_ratios_from_data
from codegreen.fecom.measurement.measurement_config import MEASUREMENT_INTERVAL_MS, CPU_FILE_SEPARATOR, WAIT_UNTIL_PRINTING_STATS_S
from codegreen.fecom.measurement.measurement_config import ENERGY_DATA_DIR, NVIDIA_SMI_FILE, PERF_FILE, START_TIMES_FILE, EXECUTION_LOG_FILE, CPU_TEMPERATURE_MODULE
from codegreen.fecom.measurement.measurement_config import CHECK_LAST_N_POINTS, CPU_STD_TO_MEAN, RAM_STD_TO_MEAN, GPU_STD_TO_MEAN, STABLE_CHECK_TOLERANCE
from codegreen.fecom.measurement.utilities import custom_print

def print_main(message: str):
    custom_print("main", message)

def quit_process(process: Popen, message: str, print_func):
    process.terminate()
    print_func(f"Terminated {message}")
    del process

def unregister_and_quit_process(process: Popen, message: str):
    """
    This will unregister all instances of quit_process in the local interpreter, so use carefully.
    Used by execution.py to quit the CPU temperature process.
    """
    atexit.unregister(quit_process)
    quit_process(process, message, print_main)

# function registered atexit by start_measurements to terminate the measurement programs
def cleanup(perf_stat, nvidia_smi):
    quit_process(nvidia_smi, "nvidia smi", print_main)
    quit_process(perf_stat, "perf stat", print_main)


# start nvidia-smi and return the process such that it can be registered by cleanup
def start_nvidia():
    # split bash command into a list, which is the required format for subprocess.Popen
    start_nvidia = shlex.split(f"nvidia-smi -i 0 --loop-ms={MEASUREMENT_INTERVAL_MS} --format=csv,noheader --query-gpu=timestamp,power.draw,temperature.gpu")

    # open the file for nvidia-smi output
    with open(NVIDIA_SMI_FILE, "w", encoding="utf-8") as nvidia_smi_file:
        # run nvidia-smi as a subprocess and continue execution of the python program
        nvidia_smi = Popen(start_nvidia, stdout=nvidia_smi_file)
    
    nvidia_smi_start_time = time.time_ns()
    print_main(f"Nvidia-smi started")
    
    return nvidia_smi, nvidia_smi_start_time


# start perf stat and return the process such that it can be registered by cleanup (similar to start_nvidia)
def start_perf():
    # equivalent procedure as with nvidia-smi for perf but perf writes to a file on its own
    start_perf = shlex.split(f"perf stat -I {MEASUREMENT_INTERVAL_MS} -e power/energy-pkg/,power/energy-ram/ -o {str(PERF_FILE)} -x \{CPU_FILE_SEPARATOR}")

    perf_stat = Popen(start_perf)

    perf_start_time = time.time_ns()
    print_main(f"Perf started")

    return perf_stat, perf_start_time


# start sensors to track CPU temperature over time
def start_sensors(print_func):
    start_sensors = shlex.split(f"python3 {CPU_TEMPERATURE_MODULE}")

    sensors = Popen(start_sensors)

    print_func(f"Sensors started")

    return sensors


# write start times to a file for further processing
def write_start_times(perf_start_time: int, nvidia_smi_start_time: int):
    """
    This method expects start times obtained from the time.time_ns() function such that
    the execution script can synchronise its timing with the perf & nvidia-smi tools.
    """
    with open(START_TIMES_FILE, "w") as f:
        f.writelines([
            f"PERF_START {perf_start_time}\n",
            f"NVIDIA_SMI_START {nvidia_smi_start_time}"
        ])


# called by the main program at initial startup or when restarting the energy measurement script through restart_measurements
def start_measurements():
    perf_stat, perf_start_time = start_perf()
    nvidia_smi, nvidia_smi_start_time = start_nvidia()
    atexit.register(cleanup, perf_stat=perf_stat, nvidia_smi=nvidia_smi)

    write_start_times(perf_start_time, nvidia_smi_start_time)
    return perf_stat, nvidia_smi


# quit, cleanup and restart all measurement programs in a way that avoids any file corruptions to the energy_measurement/out files
def restart_measurements(previous_perf_stat, previous_nvidia_smi, latest_execution):
    # unregister the previous cleanup function
    atexit.unregister(cleanup)
    # terminate the previous processes
    previous_nvidia_smi.terminate()
    del previous_nvidia_smi
    print_main(f"Quit nvidia-smi after executing {latest_execution}")
    previous_perf_stat.terminate()
    del previous_perf_stat
    print_main(f"Quit perf stat after executing {latest_execution}")

    # delete the perf & nvidia-smi files
    if PERF_FILE.is_file() and NVIDIA_SMI_FILE.is_file():
            os.remove(PERF_FILE)
            os.remove(NVIDIA_SMI_FILE)
    else:
        raise OSError("Could not find and remove perf & nvidia files")

    # restart the measurement programs
    perf_stat, nvidia_smi = start_measurements()

    return perf_stat, nvidia_smi

def print_experiment_settings():
    """
    Print the most important experiment settings such that the user
    can confirm they are correct when starting the measurement tools.
    """
    from codegreen.fecom.measurement.measurement_config import WAIT_PER_STABLE_CHECK_LOOP_S, MEASUREMENT_INTERVAL_S, CPU_MAXIMUM_TEMPERATURE, GPU_MAXIMUM_TEMPERATURE, CPU_TEMPERATURE_INTERVAL_S
    print_main(f"""
    ### Experiment Settings ###
    "wait_per_stable_check_loop_s": {WAIT_PER_STABLE_CHECK_LOOP_S},
    "tolerance": {STABLE_CHECK_TOLERANCE},
    "measurement_interval_s": {MEASUREMENT_INTERVAL_S},
    "check_last_n_points": {CHECK_LAST_N_POINTS},
    "cpu_max_temp": {CPU_MAXIMUM_TEMPERATURE},
    "gpu_max_temp": {GPU_MAXIMUM_TEMPERATURE},
    "cpu_temperature_interval_s": {CPU_TEMPERATURE_INTERVAL_S}
    """
    )

def print_stdev_mean_ratios(wait_until_printing_stats: int):
    cpu_std_mean, ram_std_mean, gpu_std_mean = calc_ratios_from_data(CHECK_LAST_N_POINTS, directory=ENERGY_DATA_DIR)
    print_main(
    f"""
    Stats after {wait_until_printing_stats} seconds:
    CPU stdev/mean ratio: {cpu_std_mean} (current) vs {CPU_STD_TO_MEAN} (config) vs {CPU_STD_TO_MEAN * (1 + STABLE_CHECK_TOLERANCE)} (config + tolerance)
    RAM stdev/mean ratio: {ram_std_mean} (current) vs {RAM_STD_TO_MEAN} (config) vs {RAM_STD_TO_MEAN * (1 + STABLE_CHECK_TOLERANCE)} (config + tolerance)
    GPU stdev/mean ratio: {gpu_std_mean} (current) vs {GPU_STD_TO_MEAN} (config) vs {GPU_STD_TO_MEAN * (1 + STABLE_CHECK_TOLERANCE)} (config + tolerance)
    If the current ratios are significantly larger than the config ones, there might be an excess number of background processes running.
    """
    )

def main():
    print_experiment_settings()
    atexit.register(print_main, "Successfully terminated the measurement application")

    # (0) Create the "out" directory if it doesn't exist
    ENERGY_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # (1) Start the energy measurement programs (perf stat & nvidia-smi).
    # Keep a reference to perf stat & nvidia-smi such that they can be terminated by the program.
    perf_stat, nvidia_smi = start_measurements()

    # (2) Create the execution log file which keeps track of the functions executed.
    # Initialise previous_execution with the initial contents of the file.
    previous_execution = f"START_MEASUREMENTS;{time.time_ns()}\n"
    with open(EXECUTION_LOG_FILE, 'w') as f:
        f.write("function_executed;time_stamp\n")
        f.write(previous_execution)

    # (3) Start the main loop and quit when receiving keyboard interrupt (Control-C)
    try:
        time_counter = 0
        check_idle_stats = True
        print_main(f"Please wait {WAIT_UNTIL_PRINTING_STATS_S} seconds to see if the machine is in a stable state")
        while(True):
            # print out stdev to mean ratios once after the specified time
            if check_idle_stats and time_counter >= WAIT_UNTIL_PRINTING_STATS_S:
                print_stdev_mean_ratios(WAIT_UNTIL_PRINTING_STATS_S)
                check_idle_stats = False

            # check the execution log: has there been a new execution?
            with open(EXECUTION_LOG_FILE, 'r') as f:
                latest_execution = f.readlines()[-1]
            
            # When the execution environment adds a new function to the log file, we want to to restart perf & nvidia-smi to clear the energy measurement files
            if latest_execution != previous_execution:
                # restart all programs, and update the references to point at the new processes
                perf_stat, nvidia_smi = restart_measurements(perf_stat, nvidia_smi, latest_execution.split(";")[0])
                previous_execution = latest_execution
            
            # this is half the time the execution environment waits before starting execution, which gives the system enough time to restart in between function calls.
            time.sleep(5)
            time_counter += 5
            continue
    except KeyboardInterrupt:
        print_main("\n\nKeyboardInterrupt by User. Shutting down the measurement application.\n")



if __name__ == "__main__":
    main()
    
