#!/usr/bin/env bash
# Run MCC-AP on Linux under Proton. Put this next to HaloAP_launcher.exe and run it
# from a terminal (the launcher asks for the server, slot and password there).
#
# Why a wrapper (see Docs/setup-linux.md): the launcher and HaloAP.dll talk over a
# named pipe that belongs to the wineserver, so MCC has to run in the launcher's
# wineserver. A normal Steam launch can't do that, so this script starts the
# launcher and then MCC itself, both with `proton runinprefix` on MCC's prefix.
# MCC then runs outside Steam's container: no overlay, and Steam won't show it
# as running.
#
# Overrides (environment variables):
#   MCC_DIR   MCC install dir (default: found through Steam's library folders)
#   PROTON    path to the `proton` script (default: Proton Hotfix, else the newest Proton)
#   STEAM_DIR Steam root (default: ~/.local/share/Steam or ~/.steam/steam)
#   HALOAP_LOG_DIR  where logs go (default: ~/.cache/haloap)
set -u

APPID=976730
HERE="$(cd "$(dirname "$0")" && pwd)"
EXE="$HERE/HaloAP_launcher.exe"
LOG_DIR="${HALOAP_LOG_DIR:-$HOME/.cache/haloap}"

die() { echo "halo-ap: $*" >&2; exit 1; }

[ -f "$EXE" ] || die "HaloAP_launcher.exe not found next to this script"

if [ -z "${STEAM_DIR:-}" ]; then
    for d in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        [ -d "$d/steamapps" ] && { STEAM_DIR="$d"; break; }
    done
fi
[ -n "${STEAM_DIR:-}" ] || die "Steam not found; set STEAM_DIR"

# Steam library folders: the main one plus every "path" in libraryfolders.vdf
libraries() {
    echo "$STEAM_DIR"
    sed -n 's/^[[:space:]]*"path"[[:space:]]*"\(.*\)"/\1/p' "$STEAM_DIR/steamapps/libraryfolders.vdf" 2>/dev/null
}

if [ -z "${MCC_DIR:-}" ]; then
    while IFS= read -r lib; do
        if [ -f "$lib/steamapps/appmanifest_$APPID.acf" ]; then
            MCC_DIR="$lib/steamapps/common/Halo The Master Chief Collection"
            break
        fi
    done < <(libraries)
fi
[ -d "${MCC_DIR:-}" ] || die "MCC install not found; set MCC_DIR"
LIBRARY="$(cd "$MCC_DIR/../../.." && pwd)"
BIN="$MCC_DIR/MCC/Binaries/Win64"
# The prefix sits in the game's library, or in the main Steam dir when the library
# can't hold one (e.g. NTFS drives)
PREFIX="$LIBRARY/steamapps/compatdata/$APPID"
[ -d "$PREFIX/pfx" ] || PREFIX="$STEAM_DIR/steamapps/compatdata/$APPID"
[ -d "$PREFIX/pfx" ] || die "no Proton prefix for MCC found; launch MCC from Steam once first"

if [ -z "${PROTON:-}" ]; then
    while IFS= read -r lib; do
        [ -x "$lib/steamapps/common/Proton Hotfix/proton" ] && { PROTON="$lib/steamapps/common/Proton Hotfix/proton"; break; }
    done < <(libraries)
fi
if [ -z "${PROTON:-}" ]; then
    PROTON="$(libraries | while IFS= read -r lib; do ls -d "$lib"/steamapps/common/Proton*/proton 2>/dev/null; done | sort -V | tail -n1)"
fi
[ -x "${PROTON:-}" ] || die "Proton not found; set PROTON to its 'proton' script"

# Windows (Z:) path of a Linux path
winpath() { printf 'Z:%s' "$(printf '%s' "$1" | tr '/' '\\')"; }

mkdir -p "$LOG_DIR"
echo "MCC:     $MCC_DIR"
echo "Proton:  $PROTON"
echo "Logs:    $LOG_DIR"

export STEAM_COMPAT_DATA_PATH="$PREFIX"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_DIR"
export HALOAP_NO_LAUNCH=1
# Also keeps the DLL from opening a console, which destabilises MCC under Proton
export HALOAP_LOG="$(winpath "$LOG_DIR/haloap-dll.log")"

# The launcher reads the game dir from here; fill it in so it doesn't have to ask
[ -s "$HERE/haloap_config.txt" ] || winpath "$MCC_DIR" > "$HERE/haloap_config.txt"

# Once the launcher has installed the mod files, start MCC in the same prefix so
# it joins the launcher's wineserver and can reach the named pipe.
(
    for _ in $(seq 1 900); do
        [ -f "$BIN/HaloAP.dll" ] && [ -f "$BIN/bink2w64_original.dll" ] && break
        sleep 1
    done
    [ -f "$BIN/HaloAP.dll" ] || { echo "halo-ap: mod files never appeared" >&2; exit 1; }
    sleep 2
    echo "halo-ap: starting MCC"
    cd "$BIN" || exit 1
    SteamAppId=$APPID SteamGameId=$APPID HALOAP_NO_LAUNCH= \
        "$PROTON" runinprefix "$BIN/MCC-Win64-Shipping.exe" -no-eac >> "$LOG_DIR/mcc.log" 2>&1
) &
watcher=$!
trap 'kill $watcher 2>/dev/null' EXIT

cd "$HERE" || exit 1
"$PROTON" runinprefix "$EXE"
