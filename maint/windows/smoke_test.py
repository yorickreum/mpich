#
# Copyright (C) by Argonne National Laboratory
#     See COPYRIGHT in top-level directory
#
# Smoke test for the Windows wheel, using only ctypes:
#
#   mpiexec -n 4 python maint/windows/smoke_test.py
#

import ctypes
import os
import sys

# MPICH handle constants (mpi.h)
MPI_COMM_WORLD = 0x44000000
MPI_INT = 0x4C000405
MPI_SUM = 0x58000003

dlldir = os.path.join(sys.prefix, "Library", "bin")
if hasattr(os, "add_dll_directory") and os.path.isdir(dlldir):
    os.add_dll_directory(dlldir)
mpi = ctypes.CDLL("libmpi-0.dll")

mpi.MPI_Init(None, None)
rank, size = ctypes.c_int(), ctypes.c_int()
mpi.MPI_Comm_rank(MPI_COMM_WORLD, ctypes.byref(rank))
mpi.MPI_Comm_size(MPI_COMM_WORLD, ctypes.byref(size))

send, total = ctypes.c_int(rank.value + 1), ctypes.c_int()
mpi.MPI_Allreduce(ctypes.byref(send), ctypes.byref(total), 1, MPI_INT, MPI_SUM, MPI_COMM_WORLD)
expected = size.value * (size.value + 1) // 2

name = ctypes.create_string_buffer(256)
namelen = ctypes.c_int()
mpi.MPI_Get_processor_name(name, ctypes.byref(namelen))
print(f"rank {rank.value}/{size.value} on {name.value.decode()}: allreduce sum = {total.value}",
      flush=True)
mpi.MPI_Finalize()
sys.exit(0 if total.value == expected else 1)
