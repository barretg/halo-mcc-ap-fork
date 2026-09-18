#!/usr/bin/env bash
# Cross-build HaloAP.dll on Linux with clang-cl + xwin (no Visual Studio).
set -euo pipefail
X="${XWIN_ROOT:-$HOME/.xwin}"
SRC="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$SRC/build-dll}"
CRT="${CRT:-/MT}"
mkdir -p "$OUT"

INC=(
  /imsvc "$X/crt/include"
  /imsvc "$X/sdk/include/ucrt"
  /imsvc "$X/sdk/include/um"
  /imsvc "$X/sdk/include/shared"
)
APP_INC=( "-I$SRC/HaloAP_Shared" "-I$SRC/HaloAP_DLL/minhook" "-I$SRC/HaloAP_DLL" )
DEFS=( /DWIN32 /DNDEBUG /DHALOAPDLL_EXPORTS /D_WINDOWS /D_USRDLL
       /DWIN32_LEAN_AND_MEAN /DNOMINMAX /D_CRT_SECURE_NO_WARNINGS )

mapfile -t CPPS < <(find "$SRC/HaloAP_DLL" -name '*.cpp' -not -path '*/minhook/*' | sort)
mapfile -t CS   < <(find "$SRC/HaloAP_DLL/minhook/src" -name '*.c' | sort)

clang-cl --target=x86_64-pc-windows-msvc /nologo /c /O2 /W0 "$CRT" \
  "${DEFS[@]}" "${INC[@]}" "${APP_INC[@]}" "${CS[@]}" /Fo"$OUT/"
clang-cl --target=x86_64-pc-windows-msvc /nologo /c /std:c++17 /EHsc /O2 /W0 "$CRT" \
  "${DEFS[@]}" "${INC[@]}" "${APP_INC[@]}" "${CPPS[@]}" /Fo"$OUT/"

lld-link /nologo /dll /machine:x64 /out:"$OUT/HaloAP.dll" "$OUT"/*.obj \
  "/libpath:$X/crt/lib/x86_64" "/libpath:$X/sdk/lib/ucrt/x86_64" "/libpath:$X/sdk/lib/um/x86_64" \
  kernel32.lib user32.lib advapi32.lib psapi.lib ws2_32.lib shell32.lib
echo "built: $OUT/HaloAP.dll"
