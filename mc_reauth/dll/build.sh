#!/usr/bin/env bash
#
# Build the mc_reauth DLL for Windows using the mingw-w64 cross-compiler.
#
# Produces:
#   build/reauth-x64.dll   (for 64-bit javaw.exe -- most modern launchers)
#   build/reauth-x86.dll   (for 32-bit javaw.exe -- common with 1.7.10)
#
# jni.h / jvmti.h are taken from your installed JDK at build time (they are
# GPL+Classpath Oracle headers and are deliberately NOT vendored into this
# MIT repo); only the Windows jni_md.h is provided here. Set JAVA_HOME, or
# have `javac` on PATH.
#
# Install the toolchain on Debian/Ubuntu with:
#   sudo apt-get install gcc-mingw-w64-x86-64 gcc-mingw-w64-i686
# On Windows build with MSYS2/MinGW or MSVC (cl) instead -- the source is
# plain C99 + Win32 + JNI/JVMTI and has no third-party dependencies.

set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
src="$here/src/reauth.c"
out="$here/build"
inc="$out/include"
mkdir -p "$inc"

# --- locate the JDK include directory --------------------------------------
if [ -z "${JAVA_HOME:-}" ]; then
    if command -v javac >/dev/null 2>&1; then
        javac_path="$(command -v javac)"
        JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$javac_path")")")"
    fi
fi
jdk_inc="${JAVA_HOME:-}/include"
if [ ! -f "$jdk_inc/jni.h" ] || [ ! -f "$jdk_inc/jvmti.h" ]; then
    echo "error: jni.h / jvmti.h not found under '$jdk_inc'." >&2
    echo "       set JAVA_HOME to a JDK (any 8+ works; headers are stable)." >&2
    exit 1
fi

# Assemble a clean include dir: JDK's jni.h/jvmti.h + our Windows jni_md.h.
cp "$jdk_inc/jni.h" "$jdk_inc/jvmti.h" "$inc/"
cp "$here/include/jni_md.h" "$inc/"

CFLAGS="-O2 -Wall -Wextra -std=c99 -I$inc -shared -static-libgcc"
LDLIBS="-lws2_32"

CC64="${CC64:-x86_64-w64-mingw32-gcc}"
CC32="${CC32:-i686-w64-mingw32-gcc}"
built=0

if command -v "$CC64" >/dev/null 2>&1; then
    echo "==> building reauth-x64.dll"
    "$CC64" $CFLAGS -o "$out/reauth-x64.dll" "$src" $LDLIBS
    built=1
else
    echo "!! $CC64 not found -- skipping 64-bit build"
fi

if command -v "$CC32" >/dev/null 2>&1; then
    echo "==> building reauth-x86.dll"
    "$CC32" $CFLAGS -o "$out/reauth-x86.dll" "$src" $LDLIBS
    built=1
else
    echo "!! $CC32 not found -- skipping 32-bit build"
fi

if [ "$built" -eq 0 ]; then
    echo "no mingw compiler found; nothing built" >&2
    exit 1
fi

echo "==> done:"
ls -l "$out"/*.dll 2>/dev/null || true
