import os
import shutil
import subprocess
from pathlib import Path
from unittest import mock

import pytest
import typer

from codegreen.main import start_energy_measurement


@pytest.fixture
def project_dir(tmp_path):
    # Create a temporary directory for the project
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()

    # Create a sample script
    script_path = project_dir / "script.py"
    script_path.write_text("print('Hello, world!')")

    return project_dir


def test_start_energy_measurement(project_dir):
    # Define the arguments for the function
    project = project_dir
    scripts = [project_dir / "script.py"]

    # Mock the get_repo_metadata function to return a dummy value
    with mock.patch("codegreen.main.get_repo_metadata") as mock_get_repo_metadata:
        mock_get_repo_metadata.return_value = {"author": "John Doe"}

        # Call the function
        start_energy_measurement(project=project, scripts=scripts)

    # Check that the patched files were created
    patched_dir = project_dir / "my_project_patched"
    assert patched_dir.exists()

    # Check that the method-level scripts were created
    method_level_scripts_dir = patched_dir / "method-level-scripts"
    assert method_level_scripts_dir.exists()

    # Check that the project-level scripts were created
    project_level_scripts_dir = patched_dir / "project-level-scripts"
    assert project_level_scripts_dir.exists()

    # Check that the original scripts were not modified
    assert (project_dir / "script.py").read_text() == "print('Hello, world!')"

    # Check that the method-level script was run successfully
    output = subprocess.check_output(["python3", str(method_level_scripts_dir / "script_method-level.py"), "1", str(project_dir / "script")])
    assert output == b"Hello, world!\n"

    # Check that the log file was created
    log_file = patched_dir / "codegreen.log"
    assert log_file.exists()

    # Check that the patched directory was deleted
    shutil.rmtree(patched_dir)
    assert not patched_dir.exists()