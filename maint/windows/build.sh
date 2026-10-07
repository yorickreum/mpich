#!/bin/sh
#
# Copyright (C) by Argonne National Laboratory
#     See COPYRIGHT in top-level directory
#
# Build MPICH for native Windows with MSYS2 (UCRT64 environment) and stage
# it for packaging.  Run from an UCRT64 shell at the top of the source tree
# (after ./autogen.sh):
#
#   maint/windows/build.sh [builddir] [stagedir]
#
# The staged tree (stagedir/{bin,include,lib}) is what maint/windows/setup.py
# turns into a wheel.

set -eu

srcdir=$(cd "$(dirname "$0")/../.." && pwd)
builddir=${1:-$srcdir/build-release}
stagedir=${2:-$srcdir/maint/windows/stage}
njobs=${NJOBS:-$(nproc)}

case "${MSYSTEM:-}" in
    UCRT64|CLANG64|MINGW64) ;;
    *) echo "run this from an MSYS2 UCRT64 (or CLANG64/MINGW64) shell" >&2; exit 1 ;;
esac

mkdir -p "$builddir"
cd "$builddir"
if test ! -f config.status; then
    "$srcdir"/configure \
        --prefix="$stagedir" \
        --with-device=ch3:sock \
        --with-pm=winexec \
        --without-hwloc \
        --disable-fortran \
        --disable-cxx \
        --disable-romio \
        --disable-doc \
        --enable-shared \
        --disable-static \
        --enable-g=none \
        --enable-fast=O2
fi
make -j "$njobs"
make install-strip

# The wheel ships DLLs, so libtool archives are of no use
rm -f "$stagedir"/lib/*.la

# Bundle the MinGW runtime DLLs our binaries depend on
for dll in $(ldd "$stagedir"/bin/*.dll "$stagedir"/bin/*.exe 2>/dev/null |
             awk '/\/(ucrt64|clang64|mingw64)\/bin\// {print $3}' | sort -u); do
    cp -v "$dll" "$stagedir"/bin/
done

# impi.dll compatibility shim.  The mpi4py wheels for Windows contain an
# extension built against Intel MPI, which shares the MPICH ABI and imports
# everything from "impi.dll".  The shim only holds export forwarders to
# libmpi-0.dll; the two data symbols mpi4py imports live in libpmpi-0.dll
# because MinGW cannot provide the weak aliases that merge the two libraries.
exports() {
    objdump -p "$1" | awk '/\[Ordinal\/Name Pointer\] Table/ {f=1; next} f && /\]/ {print $NF}'
}
shimdir="$builddir"/impi-shim
mkdir -p "$shimdir"
{
    echo "LIBRARY impi.dll"
    echo "EXPORTS"
    exports "$stagedir"/bin/libmpi-0.dll | grep -E '^P?MPIX?_' | sed 's/.*/    & = libmpi-0.&/'
    exports "$stagedir"/bin/libpmpi-0.dll | grep -E '^MPI_(UNWEIGHTED|WEIGHTS_EMPTY)$' |
        sed 's/.*/    & = libpmpi-0.& DATA/'
} > "$shimdir"/impi.def
echo '/* all exports are forwarders, see impi.def */' > "$shimdir"/impi.c
gcc -shared -s -o "$stagedir"/bin/impi.dll "$shimdir"/impi.c "$shimdir"/impi.def
