#!/usr/bin/env bash
# Build everything a release needs into build/ (untracked):
#   build/release/HaloAP-Windows/   HaloAP.dll, HaloAP_launcher.exe, Bink2w64.dll, OpenSSL DLLs
#   build/release/HaloAP-Linux/     the same files plus halo-ap.sh (runs it under Proton)
#   build/release/HaloAP-Windows.zip, HaloAP-Linux.zip
#   build/release/halo_mcc.apworld
#
# Both packages use the same launcher: on Linux it runs under Proton through
# halo-ap.sh (see Docs/setup-linux.md).
#
# Prebuilt inputs come from PREBUILT (default ../release/HaloAP):
#   Bink2w64.dll                          proxy that loads HaloAP.dll; needs MSVC to build
#   libssl-3-x64.dll, libcrypto-3-x64.dll the launcher's OpenSSL (wss://) runtime
# The OpenSSL headers and import libs the launcher links against are made from
# these DLLs and the matching OpenSSL source, and cached in build/deps.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
BUILD="$SRC/build"
PREBUILT="${PREBUILT:-$SRC/../release/HaloAP}"
REL="$BUILD/release"
OPENSSL_VERSION=3.6.2
OPENSSL_SHA256=aaf51a1fe064384f811daeaeb4ec4dce7340ec8bd893027eee676af31e83a04f
OSSL="$BUILD/deps/openssl-$OPENSSL_VERSION"
PREBUILT_FILES=(Bink2w64.dll libssl-3-x64.dll libcrypto-3-x64.dll)

for f in "${PREBUILT_FILES[@]}"; do
  [[ -f "$PREBUILT/$f" ]] || { echo "$f not found in $PREBUILT (set PREBUILT=...)" >&2; exit 1; }
done
if ! grep -aq "OpenSSL $OPENSSL_VERSION " "$PREBUILT/libcrypto-3-x64.dll"; then
  echo "$PREBUILT/libcrypto-3-x64.dll isn't OpenSSL $OPENSSL_VERSION; update OPENSSL_VERSION/OPENSSL_SHA256" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# OpenSSL headers + import libs for Windows x64
# ---------------------------------------------------------------------------
if [[ ! -f "$OSSL/lib/libssl.lib" ]]; then
  echo "== preparing OpenSSL $OPENSSL_VERSION headers and import libs"
  WORK="$BUILD/deps/work"
  rm -rf "$WORK" "$OSSL"
  mkdir -p "$WORK" "$OSSL/lib"
  TARBALL="$WORK/openssl-$OPENSSL_VERSION.tar.gz"
  curl -fsSL -o "$TARBALL" \
    "https://github.com/openssl/openssl/releases/download/openssl-$OPENSSL_VERSION/openssl-$OPENSSL_VERSION.tar.gz"
  echo "$OPENSSL_SHA256  $TARBALL" | sha256sum -c --quiet
  tar xzf "$TARBALL" -C "$WORK"
  (
    cd "$WORK/openssl-$OPENSSL_VERSION"
    # Only the generated headers are used, nothing is compiled. The VC-WIN64A
    # target won't configure under a Linux perl, so configure the mingw64 target
    # (same LLP64 settings; no mingw tools are run) and switch the system id.
    perl Configure mingw64 no-asm no-shared CC=clang > /dev/null
    for f in include/openssl/*.h.in; do
      perl -I. -Mconfigdata util/dofile.pl -oMakefile "$f" > "${f%.in}"
    done
    sed -i 's/OPENSSL_SYS_MINGW64/OPENSSL_SYS_WIN64A/g' include/openssl/configuration.h
    mkdir -p "$OSSL/include/openssl"
    cp include/openssl/*.h "$OSSL/include/openssl/"
  )
  # Import libs from the export tables of the DLLs that ship with the launcher
  for lib in libssl libcrypto; do
    python3 - "$PREBUILT/$lib-3-x64.dll" "$WORK/$lib.def" <<'EOF'
import struct, sys
dll, deffile = sys.argv[1], sys.argv[2]
d = open(dll, "rb").read()
pe = struct.unpack_from("<I", d, 0x3C)[0]
nsec = struct.unpack_from("<H", d, pe + 6)[0]
optsz = struct.unpack_from("<H", d, pe + 20)[0]
opt = pe + 24
exp_rva = struct.unpack_from("<I", d, opt + 112)[0]  # PE32+ export data directory
secs = [struct.unpack_from("<IIII", d, opt + optsz + 40 * i + 8) for i in range(nsec)]
def off(rva):
    return next(rva - va + raw for vs, va, rs, raw in secs if va <= rva < va + max(vs, rs))
e = off(exp_rva)
count, names = struct.unpack_from("<I", d, e + 24)[0], off(struct.unpack_from("<I", d, e + 32)[0])
with open(deffile, "w") as out:
    out.write(f"LIBRARY {dll.rsplit('/', 1)[-1]}\nEXPORTS\n")
    for i in range(count):
        p = off(struct.unpack_from("<I", d, names + 4 * i)[0])
        out.write(f"  {d[p:d.index(b'\0', p)].decode()}\n")
EOF
    lld-link /lib /machine:x64 "/def:$WORK/$lib.def" "/out:$OSSL/lib/$lib.lib" > /dev/null
  done
  rm -rf "$WORK"
fi

# ---------------------------------------------------------------------------
# Binaries (static CRT so players don't need the Visual C++ runtime)
# ---------------------------------------------------------------------------
echo "== building HaloAP.dll"
CRT=/MT "$SRC/build-dll-clangcl.sh" "$BUILD/dll"
echo "== building HaloAP_launcher.exe"
CRT=/MT OPENSSL_DIR="$OSSL" "$SRC/build-launcher-clangcl.sh" "$BUILD/launcher"

# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------
rm -rf "$REL"
for pkg in HaloAP-Windows HaloAP-Linux; do
  mkdir -p "$REL/$pkg"
  cp "$BUILD/dll/HaloAP.dll" "$BUILD/launcher/HaloAP_launcher.exe" "$REL/$pkg/"
  for f in "${PREBUILT_FILES[@]}"; do cp "$PREBUILT/$f" "$REL/$pkg/"; done
done
install -m 755 "$SRC/linux/halo-ap.sh" "$REL/HaloAP-Linux/halo-ap.sh"

python3 - "$SRC/apworld" "$REL" <<'EOF'
import json, os, sys, zipfile

src, rel = sys.argv[1], sys.argv[2]

# One zip per package, files at the zip root; keep halo-ap.sh executable
for pkg in ("HaloAP-Windows", "HaloAP-Linux"):
    folder = os.path.join(rel, pkg)
    with zipfile.ZipFile(os.path.join(rel, pkg + ".zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            info = zipfile.ZipInfo.from_file(path, name)
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(path, "rb") as f:
                z.writestr(info, f.read())

# halo_mcc.apworld: the world folder, with the container version fields the
# apworld spec leaves to packaging
with zipfile.ZipFile(os.path.join(rel, "halo_mcc.apworld"), "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(os.path.join(src, "halo_mcc")):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            path = os.path.join(root, name)
            arc = os.path.relpath(path, src)
            if name == "archipelago.json":
                manifest = json.load(open(path))
                manifest.update(version=7, compatible_version=7)
                z.writestr(arc, json.dumps(manifest))
            else:
                z.write(path, arc)
EOF

echo
echo "release files in $REL:"
ls -l "$REL" "$REL/HaloAP-Windows" "$REL/HaloAP-Linux"
