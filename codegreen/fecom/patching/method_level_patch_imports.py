
import sys
from codegreen.fecom.patching.patching_config import EXPERIMENT_DIR
from codegreen.fecom.measurement.execution import before_execution as before_execution_INSERTED_INTO_SCRIPT
from codegreen.fecom.measurement.execution import after_execution as after_execution_INSERTED_INTO_SCRIPT
from codegreen.fecom.experiment.experiment_kinds import ExperimentKinds

experiment_number = sys.argv[1]
experiment_project = sys.argv[2]

EXPERIMENT_FILE_PATH = EXPERIMENT_DIR / experiment_project / f'experiment-{experiment_number}.json'

