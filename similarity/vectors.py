import numpy as np

# One place that defines how a vector is stored in Embedding.vector_data:
# 1,024 float32 numbers packed into 4,096 bytes.
DTYPE = np.float32
DIM = 1024


def vector_to_bytes(vec):
    arr = np.asarray(vec, dtype=DTYPE)
    if arr.shape != (DIM,):
        raise ValueError(f"Expected a {DIM}-number vector, got shape {arr.shape}")
    return arr.tobytes()


def bytes_to_vector(data):
    arr = np.frombuffer(bytes(data), dtype=DTYPE)
    if arr.shape != (DIM,):
        raise ValueError(f"Stored vector has shape {arr.shape}, expected ({DIM},)")
    return arr