#
# Copyright (C) by Argonne National Laboratory
#     See COPYRIGHT in top-level directory
#
# Exercise mpi4py (stock PyPI wheel) against the Windows MPICH wheel:
#
#   mpiexec -n 4 python maint/windows/mpi4py_test.py
#

import array
import sys

from mpi4py import MPI

comm = MPI.COMM_WORLD
rank, size = comm.Get_rank(), comm.Get_size()
checks = []


def check(name, ok):
    checks.append((name, bool(ok)))


# pickle-based point-to-point and collectives
obj = {"rank": rank, "data": list(range(rank + 1))}
right, left = (rank + 1) % size, (rank - 1) % size
got = comm.sendrecv(obj, dest=right, source=left)
check("sendrecv(pickle)", got["rank"] == left)
check("bcast(pickle)", comm.bcast({"root": 0} if rank == 0 else None, root=0) == {"root": 0})
check("gather(pickle)", rank != 0 or comm.gather(rank, root=0) == list(range(size)))
if rank != 0:
    comm.gather(rank, root=0)
check("allgather(pickle)", comm.allgather(rank * 2) == [2 * r for r in range(size)])

# buffer-based (no numpy needed)
sbuf = array.array("i", [rank + 1] * 8)
rbuf = array.array("i", [0] * 8)
comm.Allreduce(sbuf, rbuf, op=MPI.SUM)
check("Allreduce(buffer)", all(v == size * (size + 1) // 2 for v in rbuf))
dbuf = array.array("d", [float(rank)])
comm.Allreduce(MPI.IN_PLACE, dbuf, op=MPI.MAX)
check("Allreduce(IN_PLACE, MAX)", dbuf[0] == size - 1)
a2a_s = array.array("i", [rank * 100 + i for i in range(size)])
a2a_r = array.array("i", [0] * size)
comm.Alltoall(a2a_s, a2a_r)
check("Alltoall", list(a2a_r) == [r * 100 + rank for r in range(size)])

# nonblocking
req = comm.Isend(array.array("i", [rank]), dest=right, tag=7)
buf = array.array("i", [-1])
comm.Recv(buf, source=left, tag=7)
req.Wait()
check("Isend/Recv", buf[0] == left)

# communicator management
sub = comm.Split(color=rank % 2, key=rank)
check("Split", sub.Get_size() == (size + 1 - rank % 2) // 2)
check("Split allreduce", sub.allreduce(1) == sub.Get_size())
sub.Free()
dup = comm.Dup()
check("Dup", dup.Compare(comm) == MPI.CONGRUENT)
dup.Free()

# topology with MPI_UNWEIGHTED (data symbol forwarded by the shim)
graph = comm.Create_dist_graph_adjacent([left], [right])
src, dst, weighted = graph.Get_dist_neighbors()
check("dist_graph(unweighted)", src == [left] and dst == [right])
graph.Free()

# one-sided
win = MPI.Win.Allocate(4, disp_unit=4, comm=comm)
win.Fence()
win.Put(array.array("i", [rank]), target_rank=right)
win.Fence()
mem = array.array("i", bytes(win.tomemory()))
check("Win.Put/Fence", mem[0] == left)
win.Free()

# derived datatypes
vec = MPI.INT.Create_vector(2, 1, 2).Commit()
check("Type_vector size", vec.Get_size() == 8)
vec.Free()

ok = all(passed for _, passed in checks)
all_ok = comm.allreduce(ok, op=MPI.LAND)
if rank == 0:
    for name, passed in checks:
        print(f"{'ok  ' if passed else 'FAIL'} {name}")
    print(f"{MPI.Get_library_version().splitlines()[0]} -- {size} ranks: "
          f"{'all passed' if all_ok else 'FAILURES'}")
sys.exit(0 if all_ok else 1)
