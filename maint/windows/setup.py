#
# Copyright (C) by Argonne National Laboratory
#     See COPYRIGHT in top-level directory
#
# Package a staged native-Windows MPICH build (see build.sh) as a wheel.
# Modeled after github.com/mpi4py/mpi-publish: a data-only wheel whose files
# land under sys.prefix.  Programs go to Scripts\ (on PATH in an activated
# environment); DLLs go to Library\bin, which mpi4py searches by default and
# which mpiexec adds to the PATH of the processes it starts.
#
#   python -m pip wheel --no-build-isolation -w dist maint/windows
#

import os
import re

from setuptools import setup

try:
    from setuptools.command.bdist_wheel import bdist_wheel
except ImportError:
    from wheel.bdist_wheel import bdist_wheel


class bdist_wheel(bdist_wheel):
    def finalize_options(self):
        super().finalize_options()
        self.root_is_pure = False

    def get_tag(self):
        # binaries do not depend on the Python version or ABI
        return ("py3", "none", "win_amd64")


basedir = os.path.dirname(os.path.abspath(__file__))
stagedir = os.environ.get("STAGEDIR", os.path.join(basedir, "stage"))

with open(os.path.join(basedir, "..", "..", "maint", "version.m4")) as f:
    version = re.search(r"m4_define\(\[MPICH_VERSION_m4\],\[([^\]]+)\]", f.read()).group(1)
# PEP 440: 5.1.0a1 is already fine; "5.1.0rc1" etc. pass through unchanged

# staged subdir -> install location relative to sys.prefix
layout = {"bin": "Scripts", "include": "include", "lib": "lib"}

data_files = []
for path, dirs, files in os.walk(stagedir):
    dirs.sort()
    files.sort()
    rel = os.path.relpath(path, stagedir).replace(os.sep, "/")
    top, _, rest = rel.partition("/")
    if top not in layout:
        continue
    if top == "bin":
        # mpicc & co. are shell scripts that only work inside MSYS2
        # only mpiexec (linked statically against MPL) runs without the
        # DLLs next to it; other tools stay with the DLLs
        scripts = [f for f in files if f == "mpiexec.exe"]
        libbin = [f for f in files if f.endswith((".dll", ".exe")) and f not in scripts]
        data_files.append(("Scripts", [os.path.join(path, f) for f in scripts]))
        data_files.append(("Library/bin", [os.path.join(path, f) for f in libbin]))
        continue
    dest = layout[top] + ("/" + rest if rest else "")
    if files:
        data_files.append((dest, [os.path.join(path, f) for f in files]))

setup(
    name="mpich",
    version=version,
    license="LicenseRef-MPICH",
    license_files=["../../COPYRIGHT"],
    description="A high performance implementation of MPI",
    long_description="MPICH (https://www.mpich.org) is a high-performance implementation "
    "of the Message Passing Interface (MPI) standard.  This is an experimental "
    "native Windows build (single node, TCP sockets).",
    long_description_content_type="text/plain",
    author="MPICH Team",
    author_email="discuss@mpich.org",
    url="https://www.mpich.org",
    packages=[],
    data_files=data_files,
    cmdclass={"bdist_wheel": bdist_wheel},
)
