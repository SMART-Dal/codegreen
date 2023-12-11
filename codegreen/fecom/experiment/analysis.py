"""
Analyse the experimental results using the data structures from data.py.
"""

import pandas as pd
from typing import List, Dict, Tuple
from pathlib import Path

from fecom.experiment.data import DataLoader, FunctionEnergyData, ProjectEnergyData
from fecom.experiment.experiment_kinds import ExperimentKinds
from fecom.patching.patching_config import EXPERIMENT_DIR


SUMMARY_DF_COLUMNS = ['function', 'exec time (s)', 'total', 'total (normalised)', 'lag time (s)', 'lag', 'lag (normalised)', 'total + lag (normalised)', 'stdev power', 'avg power']


def init_project_energy_data(project: str, experiment_kind: ExperimentKinds, first_experiment: int = 1, last_experiment: int = 10) -> ProjectEnergyData: 
    """
    Initialise a ProjectEnergyData object containing 3 lists of FunctionEnergyData objects (CPU, RAM, GPU),
    each ob which holds lists of data for one function collected over multiple experiments.
    """
    # input sanity check
    assert last_experiment >= first_experiment
    assert first_experiment >= 1

    dl = DataLoader(project, EXPERIMENT_DIR, experiment_kind)
    # get all experiment data files for this project

    # maintain backwards compatibility for experiments run without skip_calls functionality
    if not dl.skip_calls:
        function_count = len(dl.load_single_file(dl.experiment_files[0]))

    project_energy_data = ProjectEnergyData(project, experiment_kind, (last_experiment-first_experiment+1))
    
    project_energy_data.skip_calls = dl.skip_calls

    # loop through the experiment files for this project
    for exp_file in dl.experiment_files[first_experiment-1:last_experiment]:  # experiment 1 has index 0, so subtract 1 from the first_experiment variable
        # exp_data is a list of EnergyData objects for this experiment. Each list entry corresponds to a unique function executed in this experiment.
        exp_data = dl.load_single_file(exp_file)
    
        # dl.skip_calls is False if the experiment was run without the skip_calls functionality or if the skip_calls file is empty
        if not dl.skip_calls:
            # if no calls were skipped, the number of functions executed should be the same for every experiment, otherwise something went wrong
            assert len(exp_data) == function_count, f"{experiment_kind.value}/{project}/{exp_file} contains data for {len(exp_data)} functions, but it should contain {function_count}!"
        
        # loop through the individual functions measured in the experiment
        for function_name, energy_data in exp_data.items():

            # maintain backwards compatibility for experiments run without skip_calls functionality
            if not dl.skip_calls:
                # add the execution time to the list of execution times for this function, create a new list if this is the first experiment
                project_energy_data.execution_times.setdefault(function_name, []).append(energy_data.execution_time_s)

                # skip a function if it has no energy data, but keep track of it
                if not energy_data.has_energy_data:
                    project_energy_data.no_energy_functions.add(function_name)
                    continue
            # skip_calls can be None, so only check if the function is in this list if skip_calls is not None (checked in previous if statement)
            elif function_name in dl.skip_calls or not energy_data.has_energy_data: # 2nd condition: there are cases where a function is not in skip_calls but still has no energy data
                # skip a function if it is in the skip_calls file, and keep track of it
                project_energy_data.no_energy_functions.add(function_name)
                continue

            ### add CPU data
            # general data
            # initialise FunctionEnergyData objects if empty
            project_energy_data.cpu.setdefault(function_name, FunctionEnergyData()).name = energy_data.function_name
            project_energy_data.cpu[function_name].execution_time.append(energy_data.execution_time_s)
            project_energy_data.cpu[function_name].total_args_size.append(energy_data.total_args_size)
            project_energy_data.cpu[function_name].total_input_size.append(energy_data.total_input_size)
            # device-specific data
            project_energy_data.cpu[function_name].total.append(energy_data.total_cpu)
            project_energy_data.cpu[function_name].total_normalised.append(energy_data.total_cpu_normalised)
            project_energy_data.cpu[function_name].lag_time.append(energy_data.cpu_lag_time)
            project_energy_data.cpu[function_name].lag.append(energy_data.cpu_lag)
            project_energy_data.cpu[function_name].lag_normalised.append(energy_data.cpu_lag_normalised)
            project_energy_data.cpu[function_name].total_lag_normalised.append(energy_data.total_cpu_lag_normalised)
            project_energy_data.cpu[function_name].stdev_power.append(energy_data.stdev_power_cpu)
            project_energy_data.cpu[function_name].mean_power.append(energy_data.mean_power_cpu)
            project_energy_data.cpu[function_name].median_power.append(energy_data.median_power_cpu)

            ### add RAM data
            # general data
            # initialise FunctionEnergyData objects if empty
            project_energy_data.ram.setdefault(function_name, FunctionEnergyData()).name = energy_data.function_name
            project_energy_data.ram[function_name].execution_time.append(energy_data.execution_time_s)
            project_energy_data.ram[function_name].total_args_size.append(energy_data.total_args_size)
            project_energy_data.ram[function_name].total_input_size.append(energy_data.total_input_size)
            # device-specific data
            project_energy_data.ram[function_name].total.append(energy_data.total_ram)
            project_energy_data.ram[function_name].total_normalised.append(energy_data.total_ram_normalised)
            project_energy_data.ram[function_name].lag_time.append(energy_data.ram_lag_time)
            project_energy_data.ram[function_name].lag.append(energy_data.ram_lag)
            project_energy_data.ram[function_name].lag_normalised.append(energy_data.ram_lag_normalised)
            project_energy_data.ram[function_name].total_lag_normalised.append(energy_data.total_ram_lag_normalised)
            project_energy_data.ram[function_name].stdev_power.append(energy_data.stdev_power_ram)
            project_energy_data.ram[function_name].mean_power.append(energy_data.mean_power_ram)
            project_energy_data.ram[function_name].median_power.append(energy_data.median_power_ram)

            ### add GPU data
            # general data
            # initialise FunctionEnergyData objects if empty
            project_energy_data.gpu.setdefault(function_name, FunctionEnergyData()).name = energy_data.function_name
            project_energy_data.gpu[function_name].execution_time.append(energy_data.execution_time_s)
            project_energy_data.gpu[function_name].total_args_size.append(energy_data.total_args_size)
            project_energy_data.gpu[function_name].total_input_size.append(energy_data.total_input_size)
            # device-specific data
            project_energy_data.gpu[function_name].total.append(energy_data.total_gpu)
            project_energy_data.gpu[function_name].total_normalised.append(energy_data.total_gpu_normalised)
            project_energy_data.gpu[function_name].lag_time.append(energy_data.gpu_lag_time)
            project_energy_data.gpu[function_name].lag.append(energy_data.gpu_lag)
            project_energy_data.gpu[function_name].lag_normalised.append(energy_data.gpu_lag_normalised)
            project_energy_data.gpu[function_name].total_lag_normalised.append(energy_data.total_gpu_lag_normalised)
            project_energy_data.gpu[function_name].stdev_power.append(energy_data.stdev_power_gpu)
            project_energy_data.gpu[function_name].mean_power.append(energy_data.mean_power_gpu)
            project_energy_data.gpu[function_name].median_power.append(energy_data.median_power_gpu)
    
    return project_energy_data


def format_df(data_list: list, column_names: List[str]) -> pd.DataFrame:
    summary_df = pd.DataFrame(data_list, columns=column_names)
    
    # add a sum row for method-level experiments where each row value is equal to the sum of all values in its column
    if len(summary_df) > 1:
        summary_df.loc[len(summary_df)] = summary_df.sum(numeric_only=True)
        summary_df.iloc[-1,0] = "method-level (sum)"
    
    # round to 2 decimal places
    return summary_df.round(2)


def build_summary_df_median(energy_data_list: List[FunctionEnergyData]) -> pd.DataFrame:
    data_list = []
    for function_data in energy_data_list:
        data_list.append([
            function_data.name,
            function_data.median_execution_time,
            function_data.median_total,
            function_data.median_total_normalised,
            function_data.median_lag_time,
            function_data.median_lag,
            function_data.median_lag_normalised,
            function_data.median_total_lag_normalised,
            function_data.median_stdev_power,
            function_data.median_median_power
        ])
    
    return format_df(data_list, SUMMARY_DF_COLUMNS)


def build_summary_df_mean(energy_data_list: List[FunctionEnergyData]) -> pd.DataFrame:
    data_list = []
    for function_data in energy_data_list:
        data_list.append([
            function_data.name,
            function_data.mean_execution_time,
            function_data.mean_total,
            function_data.mean_total_normalised,
            function_data.mean_lag_time,
            function_data.mean_lag,
            function_data.mean_lag_normalised,
            function_data.mean_total_lag_normalised,
            function_data.mean_stdev_power,
            function_data.mean_mean_power
        ])
    return format_df(data_list, SUMMARY_DF_COLUMNS)


def prepare_total_energy_from_project(project_energy_data: ProjectEnergyData) -> Tuple[List[list], List[str]]:
    """
    Given a ProjectEnergyData object, construct a list of lists for constructing a DataFrame
    that contains total normalised energy data. Also return the column names for this DataFrame.
    """
    data_list = []
    for cpu, ram, gpu in zip(project_energy_data.cpu_data, project_energy_data.ram_data, project_energy_data.gpu_data):
        assert cpu.name == ram.name and cpu.name == gpu.name, "The hardware components should list the functions in the same order."
        data_list.append([
            cpu.name,
            cpu.mean_execution_time,
            cpu.mean_total_normalised,
            cpu.median_total_normalised,
            ram.mean_total_normalised,
            ram.median_total_normalised,
            gpu.mean_total_normalised,
            gpu.median_total_normalised
        ])
    
    column_names = ["function", "run time", "CPU (mean)", "CPU (median)", "RAM (mean)", "RAM (median)", "GPU (mean)", "GPU (median)"]

    return data_list, column_names

def prepare_total_energy_and_size_from_project(project_energy_data: ProjectEnergyData) -> Tuple[List[list], List[str]]:
    """
    Given a ProjectEnergyData object, construct a list of lists for constructing a DataFrame
    that contains total normalised energy data. Also return the column names for this DataFrame.
    """
    data_list = []
    for cpu, ram, gpu in zip(project_energy_data.cpu_data, project_energy_data.ram_data, project_energy_data.gpu_data):
        assert cpu.name == ram.name and cpu.name == gpu.name, "The hardware components should list the functions in the same order."
        data_list.append([
            cpu.name,
            cpu.mean_execution_time,
            cpu.mean_total_normalised,
            cpu.median_total_normalised,
            cpu.max_total_normalised,
            cpu.min_total_normalised,
            ram.mean_total_normalised,
            ram.median_total_normalised,
            ram.max_total_normalised,
            ram.min_total_normalised,
            gpu.mean_total_normalised,
            gpu.median_total_normalised,
            gpu.max_total_normalised,
            gpu.min_total_normalised,
            cpu.mean_total_args_size,
            cpu.median_total_args_size
        ])
    
    column_names = ["function", "run time", "CPU (mean)", "CPU (median)","CPU (max)", "CPU (min)" ,"RAM (mean)", "RAM (median)", "RAM (max)", "RAM (min)","GPU (mean)", "GPU (median)", "GPU (max)", "GPU (min)", "Args Size (mean)", "Args Size (median)"]

    return data_list, column_names


def build_total_energy_df(method_level_energy: ProjectEnergyData, project_level_energy: ProjectEnergyData) -> pd.DataFrame:
    """
    Construct a DataFrame containing total normalised method-level and project-level energy.
    Used to evaluate RQ1.
    """
    data_list, column_names = prepare_total_energy_from_project(method_level_energy)
    total_energy_df = format_df(data_list, column_names)
    
    data_list_project_level, _ = prepare_total_energy_from_project(project_level_energy)
    total_energy_df.loc[len(total_energy_df)] = data_list_project_level[0]
    
    return total_energy_df

def build_total_energy_and_size_df(method_level_energy: ProjectEnergyData) -> pd.DataFrame:
    """
    Construct a DataFrame containing total normalised method-level and project-level energy.
    Used to evaluate RQ1.
    """
    data_list, column_names = prepare_total_energy_and_size_from_project(method_level_energy)
    total_energy_df = pd.DataFrame(data_list, columns=column_names)
    
    return total_energy_df


def export_summary_to_latex(output_dir: Path, summary_dfs: Dict[str, pd.DataFrame]):
    """
    Write a given set of summary dfs returned by create_summary() to latex files.
    """
    for name, df in summary_dfs.items():
        df.style.format(precision=2).to_latex(buf = output_dir/f"{name}.tex")

def export_summary_to_csv(output_dir: Path, summary_dfs: Dict[str, pd.DataFrame]):
    """
    Write a given set of summary dfs returned by create_summary() to csv files.
    """
    
    for name, df in summary_dfs.items():
        csv_path = output_dir / f"{name}.csv"
        
        with open(csv_path, 'w') as csv_file:
            writer = csv.writer(csv_file)

            # Write column headers 
            writer.writerow(df.columns)

            # Write each row to the csv
            for index, row in df.iterrows():
                writer.writerow(row)

def create_summary(project_energy_data: ProjectEnergyData) -> Dict[str, pd.DataFrame]:
    cpu_summary_mean = build_summary_df_mean(project_energy_data.cpu_data)
    ram_summary_mean = build_summary_df_mean(project_energy_data.ram_data)
    gpu_summary_mean = build_summary_df_mean(project_energy_data.gpu_data)

    cpu_summary_median = build_summary_df_median(project_energy_data.cpu_data)
    ram_summary_median = build_summary_df_median(project_energy_data.ram_data)
    gpu_summary_median = build_summary_df_median(project_energy_data.gpu_data)

    print(f"\n### SUMMARY FOR {project_energy_data.name} | {project_energy_data.experiment_kind.value} ###\n")
    print("Mean CPU results (Joules)")
    print(cpu_summary_mean)
    print("\nMedian CPU results (Joules)")
    print(cpu_summary_median)
    print("\n###=======###\n")
    print("Mean RAM results (Joules)")
    print(ram_summary_mean)
    print("\nMedian RAM results (Joules)")
    print(ram_summary_median)
    print("\n###=======###\n")
    print("Mean GPU results (Joules)")
    print(gpu_summary_mean)
    print("\nMedian GPU results (Joules)")
    print(gpu_summary_median)
    print("\n###=======###\n")

    return {
        "cpu_summary_mean": cpu_summary_mean,
        "ram_summary_mean": ram_summary_mean,
        "gpu_summary_mean": gpu_summary_mean,
        "cpu_summary_median": cpu_summary_median,
        "ram_summary_median": ram_summary_median,
        "gpu_summary_median": gpu_summary_median,
    }


if __name__ == "__main__":
    project_name = "distribute/custom_training"
    method_level_data = init_project_energy_data(project_name, ExperimentKinds.METHOD_LEVEL)
    print(method_level_data.no_energy_functions)
    print(f"Number of functions: {len(method_level_data)}")
    create_summary(method_level_data)

    project_level_data = init_project_energy_data(project_name, ExperimentKinds.PROJECT_LEVEL, first_experiment=1)
    print(build_total_energy_df(method_level_data, project_level_data))

    # method_level_energies = [method_level_data]

    # project_name = "keras/classification"
    # method_level_data = init_project_energy_data(project_name, ExperimentKinds.METHOD_LEVEL, first_experiment=1)
    # method_level_energies.append(method_level_data)

    # from fecom.experiment.plot import plot_total_energy_vs_execution_time
    # plot_total_energy_vs_execution_time(method_level_energies)