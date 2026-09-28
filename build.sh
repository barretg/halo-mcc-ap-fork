#!/usr/bin/env bash
# Build everything a release needs into build/ (untracked):
#   build/release/HaloAP/      HaloAP.dll, HaloAP_launcher.exe, Bink2w64.dll
#   build/release/HaloAP.zip   the folder above, zipped
#   build/release/halo_mcc.apworld
#
# Bink2w64.dll (the proxy that loads HaloAP.dll) still needs MSVC to build, so
# it's copied from PREBUILT (default ../release/HaloAP). Override with
#   PREBUILT=/path/to/dir ./build.sh
#
# Note: the clang-cl launcher is built without SSL (see build-launcher-clangcl.sh),
# so it can only connect to ws:// servers, not wss://.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
BUILD="$SRC/build"
PREBUILT="${PREBUILT:-$SRC/../release/HaloAP}"
REL="$BUILD/release"

if [[ ! -f "$PREBUILT/Bink2w64.dll" ]]; then
  echo "Bink2w64.dll not found in $PREBUILT (set PREBUILT=...)" >&2
  exit 1
fi

rm -rf "$REL"
mkdir -p "$REL/HaloAP"

# Static CRT so players don't need the Visual C++ runtime installed
CRT=/MT "$SRC/build-dll-clangcl.sh" "$BUILD/dll"
CRT=/MT "$SRC/build-launcher-clangcl.sh" "$BUILD/launcher"

cp "$BUILD/dll/HaloAP.dll" "$BUILD/launcher/HaloAP_launcher.exe" "$PREBUILT/Bink2w64.dll" "$REL/HaloAP/"

python3 - "$SRC/apworld" "$REL" <<'EOF'
import json, os, sys, zipfile

src, rel = sys.argv[1], sys.argv[2]

# HaloAP.zip: the release folder's files at the zip root
with zipfile.ZipFile(os.path.join(rel, "HaloAP.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    folder = os.path.join(rel, "HaloAP")
    for name in sorted(os.listdir(folder)):
        z.write(os.path.join(folder, name), name)

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
ls -l "$REL" "$REL/HaloAP"
