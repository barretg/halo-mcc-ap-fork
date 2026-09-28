#!/usr/bin/env bash
# Cross-build HaloAP_launcher.exe on Linux with clang-cl + xwin (no Visual Studio).
set -euo pipefail
X="${XWIN_ROOT:-$HOME/.xwin}"
SRC="$(cd "$(dirname "$0")" && pwd)"
CRT="${CRT:-/MD}"
OUT="${1:-$SRC/build-clangcl}"
mkdir -p "$OUT"

INC=(
  /imsvc "$X/crt/include"
  /imsvc "$X/sdk/include/ucrt"
  /imsvc "$X/sdk/include/um"
  /imsvc "$X/sdk/include/shared"
)
APP_INC=(
  "-I$SRC/HaloAP_Shared"
  "-I$SRC/HaloAP_launcher"
  "-I$SRC/HaloAP_launcher/thirdparty/wswrap"
  "-I$SRC/HaloAP_launcher/thirdparty/apclientpp"
  "-I$SRC/HaloAP_launcher/thirdparty/json/include"
  "-I$SRC/HaloAP_launcher/thirdparty/websocketpp"
  "-I$SRC/HaloAP_launcher/thirdparty/asio/include"
  "-I$SRC/HaloAP_launcher/thirdparty/valijson/include"
)
DEFS=(
  /DASIO_STANDALONE /DAP_NO_SCHEMA /D_WIN32_WINNT=0x0600
  /DWIN32_LEAN_AND_MEAN /DNOMINMAX /DNDEBUG
  /DWSWRAP_NO_COMPRESSION
  /D_CRT_SECURE_NO_WARNINGS
)
LIBS=(ws2_32.lib crypt32.lib shell32.lib kernel32.lib user32.lib advapi32.lib ole32.lib oleaut32.lib)
LIBPATHS=()

# SSL (wss://) needs OpenSSL headers and import libs for Windows x64: set
# OPENSSL_DIR to a dir with include/openssl/ and lib/{libssl,libcrypto}.lib
# (build.sh prepares one). The exe then needs libssl-3-x64.dll and
# libcrypto-3-x64.dll next to it. Without OPENSSL_DIR the build is ws:// only.
if [[ -n "${OPENSSL_DIR:-}" ]]; then
  APP_INC+=( "-I$OPENSSL_DIR/include" )
  DEFS+=( /DOPENSSL_API_COMPAT=0x10100000L )
  LIBS+=( libssl.lib libcrypto.lib )
  LIBPATHS+=( "/libpath:$OPENSSL_DIR/lib" )
else
  DEFS+=( /DWSWRAP_NO_SSL )
  echo "OPENSSL_DIR not set: building without SSL (ws:// only)"
fi

clang-cl --target=x86_64-pc-windows-msvc \
  /std:c++17 /EHsc "$CRT" /O2 /W0 /nologo -fuse-ld=lld \
  "${DEFS[@]}" "${INC[@]}" "${APP_INC[@]}" \
  "$SRC/HaloAP_launcher/main.cpp" \
  "$SRC/HaloAP_launcher/ap_bridge.cpp" \
  "$SRC/HaloAP_launcher/pipe_server.cpp" \
  /Fo"$OUT/" /Fe"$OUT/HaloAP_launcher.exe" \
  /link /subsystem:console /machine:x64 \
    "/libpath:$X/crt/lib/x86_64" \
    "/libpath:$X/sdk/lib/ucrt/x86_64" \
    "/libpath:$X/sdk/lib/um/x86_64" \
    "${LIBPATHS[@]}" "${LIBS[@]}"
echo "built: $OUT/HaloAP_launcher.exe"
