#!/usr/bin/env bash
# Unmodded MCC (no EAC) + x64dbg in the same Proton prefix / wineserver.
# Both go through the same Proton's `runinprefix` so they share one wineserver;
# plain `wine` with WINEPREFIX would start a second, incompatible wineserver.
set -u
APPID=976730
GAME_ROOT="/mnt/win/f/SteamLibrary/steamapps/common/Halo The Master Chief Collection"
BIN="$GAME_ROOT/MCC/Binaries/Win64"
PROTON="/mnt/win/f/SteamLibrary/steamapps/common/Proton Hotfix/proton"
X64DBG="$HOME/Applications/x64dbg/release/x64/x64dbg.exe"
LOG="$HOME/.cache/ap-launcher/mcc-dbg.log"

pgrep -x steam >/dev/null || { echo "Start Steam first"; exit 1; }
[ -f "$BIN/bink2w64_original.dll" ] && { echo "Mod files still installed -- run halo-ap.sh cleanup first"; exit 1; }
mkdir -p "$(dirname "$LOG")"

export STEAM_COMPAT_DATA_PATH="$HOME/.local/share/Steam/steamapps/compatdata/$APPID"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.local/share/Steam"
# `runinprefix` skips Proton's prefix setup, which is where the DXVK / vkd3d-proton
# overrides get added. Without them Wine falls back to builtin wined3d (OpenGL),
# which is slow for H2/H3 and crashes H4 at mission_start.
# Applied to MCC only: with them exported for x64dbg too, attaching crashed both.
MCC_OVERRIDES="d3d11,d3d10core,d3d9,dxgi,d3d12,d3d12core=n${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"

( cd "$BIN" && SteamAppId=$APPID SteamGameId=$APPID WINEDLLOVERRIDES="$MCC_OVERRIDES" \
    "$PROTON" runinprefix "$BIN/MCC-Win64-Shipping.exe" -no-eac >>"$LOG" 2>&1 ) &

sleep 8   # let MCC create the wineserver first
cd "$(dirname "$X64DBG")"
"$PROTON" runinprefix "$X64DBG" >>"$LOG" 2>&1 &
wait
