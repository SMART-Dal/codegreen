import tensorflow as tf
import sys
from codegreen.fecom.patching.patching_config import EXPERIMENT_DIR
from codegreen.fecom.measurement.execution import before_execution as before_execution_INSERTED_INTO_SCRIPT
from codegreen.fecom.measurement.execution import after_execution as after_execution_INSERTED_INTO_SCRIPT
from codegreen.fecom.experiment.experiment_kinds import ExperimentKinds
experiment_number = sys.argv[1]
experiment_project = sys.argv[2]
EXPERIMENT_FILE_PATH = EXPERIMENT_DIR / ExperimentKinds.METHOD_LEVEL.value / experiment_project / f'experiment-{experiment_number}.json'
print('TensorFlow version:', tf.__version__)
mnist = tf.keras.datasets.mnist
((x_train, y_train), (x_test, y_test)) = mnist.load_data()
(x_train, x_test) = (x_train / 255.0, x_test / 255.0)
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.models.Sequential()')
model = tf.keras.models.Sequential([tf.keras.layers.Flatten(input_shape=(28, 28)), tf.keras.layers.Dense(128, activation='relu'), tf.keras.layers.Dropout(0.2), tf.keras.layers.Dense(10)])
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.models.Sequential()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/beginner.ipynb', 'api_call_line': 7}, method_object=None, function_args=[[tf.keras.layers.Flatten(input_shape=(28, 28)), tf.keras.layers.Dense(128, activation='relu'), tf.keras.layers.Dropout(0.2), tf.keras.layers.Dense(10)]], function_kwargs=None)
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.models.Sequential(x_train[:1]).numpy()')
predictions = model(x_train[:1]).numpy()
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.models.Sequential(x_train[:1]).numpy()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/beginner.ipynb', 'api_call_line': 13}, method_object=model, function_args=None, function_kwargs=None)
predictions
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.nn.softmax(predictions).numpy()')
tf.nn.softmax(predictions).numpy()
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.nn.softmax(predictions).numpy()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/beginner.ipynb', 'api_call_line': 15}, method_object=None, function_args=None, function_kwargs=None)
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.losses.SparseCategoricalCrossentropy()')
loss_fn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.losses.SparseCategoricalCrossentropy()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/beginner.ipynb', 'api_call_line': 16}, method_object=None, function_args=None, function_kwargs={'from_logits': True})
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.losses.SparseCategoricalCrossentropy(y_train[:1], predictions).numpy()')
loss_fn(y_train[:1], predictions).numpy()
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.losses.SparseCategoricalCrossentropy(y_train[:1], predictions).numpy()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/beginner.ipynb', 'api_call_line': 17}, method_object=loss_fn, function_args=None, function_kwargs=None)
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.models.Sequential.compile()')
model.compile(optimizer='adam', loss=loss_fn, metrics=['accuracy'])
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.models.Sequential.compile()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/beginner.ipynb', 'api_call_line': 18}, method_object=model, function_args=None, function_kwargs={'optimizer': 'adam', 'loss': loss_fn, 'metrics': ['accuracy']})
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.models.Sequential.fit()')
model.fit(x_train, y_train, epochs=5)
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.models.Sequential.fit()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/beginner.ipynb', 'api_call_line': 21}, method_object=model, function_args=[x_train, y_train], function_kwargs={'epochs': 5})
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.models.Sequential.evaluate()')
model.evaluate(x_test, y_test, verbose=2)
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.models.Sequential.evaluate()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/beginner.ipynb', 'api_call_line': 22}, method_object=model, function_args=[x_test, y_test], function_kwargs={'verbose': 2})
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.Sequential()')
probability_model = tf.keras.Sequential([model, tf.keras.layers.Softmax()])
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.Sequential()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/beginner.ipynb', 'api_call_line': 23}, method_object=None, function_args=[[model, tf.keras.layers.Softmax()]], function_kwargs=None)
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.Sequential()')
probability_model(x_test[:5])
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.Sequential()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/beginner.ipynb', 'api_call_line': 27}, method_object=probability_model, function_args=[x_test[:5]], function_kwargs=None)