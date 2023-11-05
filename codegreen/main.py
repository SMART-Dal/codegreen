import typer
from rich import print
from rich.markdown import Markdown
from codegreen.fecom.measurement import start_measurement
from typing_extensions import Annotated
from pathlib import Path
from typing import List, Optional
import shutil
import datetime

import subprocess
from codegreen.fecom.patching.patching_config import METHOD_LEVEL_PATCHING_SCRIPT_PATH, EXPERIMENT_DIR
from codegreen.fecom.patching.repo_patching import patch_project
from codegreen.utils.metadata import get_repo_metadata, get_script_path
from codegreen import __version__
import os

app = typer.Typer(rich_markup_mode="rich",help="[green]🍃 CodeGreen: Your Passport to a Greener Code! 🍃[/green]")

# @app.callback()
# def version():
#     print(f"{__version__}")
#     raise typer.Exit()

# @app.callback()
# def main(
#     version: bool = typer.Option(
#         None, "--version", callback=version, 
#         help="Print version and exit")
# ):
#    '''
#    This is the main entry point for the codegreen package.
#    '''

@app.command()
def run_energy_profiler():
    """
    This command will start the energy measurement server
    """
    print("Starting measurement...")
    start_measurement.main()

@app.command()
def start_energy_measurement(
    project : Annotated[Path,typer.Option(help="Path to the source code of the project to be measured.")],
    scripts : Annotated[List[Path],typer.Option(help="List of paths to the project scripts to be measured.")] = [],
):
    """
    This command will start running the scripts and collecting data for energy measurement.
    """
    # Start patching all the files in the argument and store them in the same location as the original file with suffix "_patched"
    project = project.resolve()
    patched_dir = project.parent / (project.stem + "_patched")
    metadata = get_repo_metadata(project)
    print("metadata",metadata)
    method_level_python_scripts, project_level_python_scripts, og_python_scripts, scripts_with_target_framework = patch_project(patched_dir,project,metadata)
    print("method_level_python_scripts",method_level_python_scripts)

    # create a list with json objects having filepaths of scripts_with_target_framework and their corresponding execution status
    # This will be used to determine if the script was executed successfully after patching and also contain logs for the file
    scripts_execution_metadata = []
    script_status = {}
    for script in scripts_with_target_framework:
        # get file name from the script_to_run path with removed "_method-level.py" substring
        base_script_path = os.path.basename(script).replace("_method-level.py","")
        script_status[str(base_script_path)] = "not_executed_yet"
    
    # store the metadata of the experiment in the experiment directory
    with open(EXPERIMENT_DIR/ project.stem / "scripts_execution_metadata.json", "w") as f:
        f.write(str(script_status))

    if scripts:
        # run the patched files in the provided sequence in arguments
        for idx, script in enumerate(scripts):
            # script = script.resolve()
            print(f"Running {script}...")
            execution_metadata = {}
            base_path, ext = os.path.splitext(script)
            # print("base script path is: ",base_path)
            execution_metadata["script_name"] = script
            # script_status[base_path] = "started_execution"

            print("script path is: ",str(patched_dir/(base_path+ "_method-level.py"))," method level script is: ", method_level_python_scripts)

            script_to_run = get_script_path(str(base_path+ "_method-level.py"), method_level_python_scripts)
            
            execution_metadata["start_time"] = datetime.datetime.now().isoformat()
            # Start the subprocess
            process = subprocess.Popen(['python3', script_to_run,"1",base_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

            output = []
            # Capture and print the output in real-time and store in a file
            with open(EXPERIMENT_DIR / base_path / "execution_log.json", "w") as f:
                for line in process.stdout:
                    print(line, end='')
                    f.write(line)
                    output.append(line)

            # Wait for the subprocess to complete
            process.wait()

            execution_metadata["end_time"] = datetime.datetime.now().isoformat()
            execution_metadata["output"] = output
            execution_metadata["return_code"] = process.returncode

            if process.returncode == 0:
                print(f"{script} completed successfully.")
                script_status[base_path] = "completed_successfully"

            else:
                print(f"Error running {script}. Return code: {process.returncode}")
                script_status[base_path] = "completed_with_error"
            
            # Add the execution metadata to the list
            scripts_execution_metadata.append(execution_metadata)

            # write script_status to the file
            with open(EXPERIMENT_DIR/ project.stem / "scripts_execution_metadata.json", "w") as f:
                f.write(str(script_status))
            print("+-----------------------------------------------+")
    else:
        print("[bold yellow]Default script execution:[/bold yellow]No scripts provided, running all scripts with the target framework")
        for idx, script_to_run in enumerate(scripts_with_target_framework):

            execution_metadata = {}
            # get file name from the script_to_run path with removed "_method-level.py" substring
            base_path = os.path.basename(script_to_run).replace("_method-level.py","")
            execution_metadata["script_name"] = base_path+".py"
            script_status[base_path] = "started_execution"

            print(f"Running {base_path}...")

            execution_metadata["start_time"] = datetime.datetime.now().isoformat()

            # Start the subprocess
            process = subprocess.Popen(['python3', script_to_run,"1",base_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            output = []

            # Capture and print the output in real-time and store in a file
            with open(EXPERIMENT_DIR / base_path / "execution_log.json", "w") as f:
                for line in process.stdout:
                    print(line, end='')
                    f.write(line)
                    output.append(line)

            # Wait for the subprocess to complete
            process.wait()

            execution_metadata["end_time"] = datetime.datetime.now().isoformat()
            execution_metadata["output"] = output
            execution_metadata["return_code"] = process.returncode

            if process.returncode == 0:
                print(f"{script_to_run} completed successfully.")
                script_status[base_path] = "completed_successfully"
            else:
                print(f"Error running {script_to_run}. Return code: {process.returncode}")
                script_status[base_path] = "completed_with_error"
            
            # Add the execution metadata to the list
            scripts_execution_metadata.append(execution_metadata)
            print("+-----------------------------------------------+")

    # store the data and log

    # Delete the patched directory
    # shutil.rmtree(patched_dir)
    # print(f"Deleted {patched_dir}")

    # stop measurement process

    # store scripts_execution_metadata in a file
    with open(EXPERIMENT_DIR/ project.stem / "scripts_execution_metadata.json", "w") as f:
        f.write(str(scripts_execution_metadata))

# only use this by uncommenting for testing purposes
if __name__ == "__main__":
    app()