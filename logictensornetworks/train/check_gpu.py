import torch
import sys
import tensorflow as tf
print(torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    print(torch.cuda.get_device_name(i))
print("GPUs:", tf.config.list_physical_devices("GPU"))

print(sys.executable)
print(tf.__file__)
print(tf.config.list_physical_devices('GPU'))