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
from tensorflow.keras.layers import Dense, Flatten, Conv2D
from tensorflow.keras import Model
mnist = tf.keras.datasets.mnist
((x_train, y_train), (x_test, y_test)) = mnist.load_data()
(x_train, x_test) = (x_train / 255.0, x_test / 255.0)
x_train = x_train[..., tf.newaxis].astype('float32')
x_test = x_test[..., tf.newaxis].astype('float32')
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.data.Dataset.from_tensor_slices((x_train, y_train)).shuffle(10000).batch()')
train_ds = tf.data.Dataset.from_tensor_slices((x_train, y_train)).shuffle(10000).batch(32)
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.data.Dataset.from_tensor_slices((x_train, y_train)).shuffle(10000).batch()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 13}, method_object=None, function_args=[32], function_kwargs=None)
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.data.Dataset.from_tensor_slices((x_test, y_test)).batch()')
test_ds = tf.data.Dataset.from_tensor_slices((x_test, y_test)).batch(32)
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.data.Dataset.from_tensor_slices((x_test, y_test)).batch()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 16}, method_object=None, function_args=[32], function_kwargs=None)

class MyModel(Model):

    def __init__(self):
        super(MyModel, self).__init__()
        start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.layers.Conv2D()')
        self.conv1 = Conv2D(32, 3, activation='relu')
        after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.layers.Conv2D()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 20}, method_object=None, function_args=[32, 3], function_kwargs={'activation': 'relu'})
        start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.layers.Flatten()')
        self.flatten = Flatten()
        after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.layers.Flatten()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 21}, method_object=None, function_args=None, function_kwargs=None)
        start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.layers.Dense()')
        self.d1 = Dense(128, activation='relu')
        after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.layers.Dense()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 22}, method_object=None, function_args=[128], function_kwargs={'activation': 'relu'})
        start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.layers.Dense()')
        self.d2 = Dense(10)
        after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.layers.Dense()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 23}, method_object=None, function_args=[10], function_kwargs=None)

    def call(self, x):
        x = self.conv1(x)
        x = self.flatten(x)
        x = self.d1(x)
        return self.d2(x)
model = MyModel()
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.losses.SparseCategoricalCrossentropy()')
loss_object = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.losses.SparseCategoricalCrossentropy()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 32}, method_object=None, function_args=None, function_kwargs={'from_logits': True})
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.optimizers.Adam()')
optimizer = tf.keras.optimizers.Adam()
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.optimizers.Adam()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 34}, method_object=None, function_args=None, function_kwargs=None)
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean()')
train_loss = tf.keras.metrics.Mean(name='train_loss')
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 35}, method_object=None, function_args=None, function_kwargs={'name': 'train_loss'})
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy()')
train_accuracy = tf.keras.metrics.SparseCategoricalAccuracy(name='train_accuracy')
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 36}, method_object=None, function_args=None, function_kwargs={'name': 'train_accuracy'})
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean()')
test_loss = tf.keras.metrics.Mean(name='test_loss')
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 38}, method_object=None, function_args=None, function_kwargs={'name': 'test_loss'})
start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy()')
test_accuracy = tf.keras.metrics.SparseCategoricalAccuracy(name='test_accuracy')
after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 39}, method_object=None, function_args=None, function_kwargs={'name': 'test_accuracy'})

@tf.function
def train_step(images, labels):
    with tf.GradientTape() as tape:
        start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.Model()')
        predictions = model(images, training=True)
        after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.Model()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 43}, method_object=model, function_args=[images], function_kwargs={'training': True})
        start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.losses.SparseCategoricalCrossentropy()')
        loss = loss_object(labels, predictions)
        after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.losses.SparseCategoricalCrossentropy()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 44}, method_object=loss_object, function_args=[labels, predictions], function_kwargs=None)
    gradients = tape.gradient(loss, model.trainable_variables)
    start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.optimizers.Adam.apply_gradients()')
    optimizer.apply_gradients(zip(gradients, model.trainable_variables))
    after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.optimizers.Adam.apply_gradients()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 46}, method_object=optimizer, function_args=[zip(gradients, model.trainable_variables)], function_kwargs=None)
    start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean()')
    train_loss(loss)
    after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 48}, method_object=train_loss, function_args=[loss], function_kwargs=None)
    start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy()')
    train_accuracy(labels, predictions)
    after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 49}, method_object=train_accuracy, function_args=[labels, predictions], function_kwargs=None)

@tf.function
def test_step(images, labels):
    start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.Model()')
    predictions = model(images, training=False)
    after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.Model()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 52}, method_object=model, function_args=[images], function_kwargs={'training': False})
    start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.losses.SparseCategoricalCrossentropy()')
    t_loss = loss_object(labels, predictions)
    after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.losses.SparseCategoricalCrossentropy()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 53}, method_object=loss_object, function_args=[labels, predictions], function_kwargs=None)
    start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean()')
    test_loss(t_loss)
    after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 55}, method_object=test_loss, function_args=[t_loss], function_kwargs=None)
    start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy()')
    test_accuracy(labels, predictions)
    after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 56}, method_object=test_accuracy, function_args=[labels, predictions], function_kwargs=None)
EPOCHS = 5
for epoch in range(EPOCHS):
    start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean.reset_states()')
    train_loss.reset_states()
    after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean.reset_states()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 60}, method_object=train_loss, function_args=None, function_kwargs=None)
    start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy.reset_states()')
    train_accuracy.reset_states()
    after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy.reset_states()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 61}, method_object=train_accuracy, function_args=None, function_kwargs=None)
    start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean.reset_states()')
    test_loss.reset_states()
    after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.Mean.reset_states()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 62}, method_object=test_loss, function_args=None, function_kwargs=None)
    start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy.reset_states()')
    test_accuracy.reset_states()
    after_execution_INSERTED_INTO_SCRIPT(start_times=start_times_INSERTED_INTO_SCRIPT, experiment_file_path=EXPERIMENT_FILE_PATH, function_to_run='tensorflow.keras.metrics.SparseCategoricalAccuracy.reset_states()', project_metadata={'script_path': '/home/saurabh/codegreen/dummy_patched/quickstart/advanced.ipynb', 'api_call_line': 63}, method_object=test_accuracy, function_args=None, function_kwargs=None)
    for (images, labels) in train_ds:
        train_step(images, labels)
    for (test_images, test_labels) in test_ds:
        test_step(test_images, test_labels)
    print(f'Epoch {epoch + 1}, Loss: {train_loss.result()}, Accuracy: {train_accuracy.result() * 100}, Test Loss: {test_loss.result()}, Test Accuracy: {test_accuracy.result() * 100}')