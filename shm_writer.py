from multiprocessing import shared_memory
import numpy as np
def write_to_shm(frame):
    shm = shared_memory.SharedMemory(create=True, size=frame.nbytes)
    np.ndarray(frame.shape, dtype=frame.dtype, buffer=shm.buf)[:] = frame
