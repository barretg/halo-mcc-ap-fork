# Setup Guide — Linux (Proton)

MCC:AP runs on Linux under Proton. The mod DLL and the launcher are still
Windows binaries running in MCC's Proton prefix — nothing here is a native
Linux port.

Verified on Arch Linux, Proton Hotfix, MCC from the Steam Windows depot.

## Why a wrapper script is needed

The launcher and `HaloAP.dll` talk over the named pipe `\\.\pipe\HaloAP`. A
named pipe belongs to the **wineserver**, so both processes must be in the same
one. That rules out letting Steam start the game:

* Steam always launches a Proton game with Proton's `waitforexitandrun` verb,
  which runs `wineserver -w` first and refuses to start the game until the
  prefix's wineserver has exited — and the launcher *is* that wineserver. The
  launch either hangs forever at "Waiting for DLL to connect", or Proton tears
  the launcher down (the launcher dies with signal 9).

So on Linux the launcher must not launch the game itself. Set
`HALOAP_NO_LAUNCH=1` and start `MCC-Win64-Shipping.exe` from the wrapper with
`proton runinprefix` on the same prefix, so it joins the launcher's wineserver.

Trade-off: MCC then runs outside Steam's pressure-vessel container, so there is
no Steam overlay and Steam does not show the game as running.

## Required environment

| Variable | Value | Why |
| --- | --- | --- |
| `HALOAP_NO_LAUNCH` | `1` | Suppress the launcher's `steam://launch/...` call — see above. |
| `HALOAP_NO_CONSOLE` | `1` | **Required.** `AllocConsole()` inside a Proton-run MCC destabilises the game: the title screen throws "Fatal Error" and mission select freezes. With the console suppressed the same build plays normally. |
| `HALOAP_LOG` | a Windows path, e.g. `Z:\tmp\haloap-dll.log` | Optional; sends the DLL's output to a file (and also suppresses the console). The wine console it would otherwise allocate cannot be scrolled back or captured. |

## Running it

Start the launcher with **`proton runinprefix`**, not `proton run`. `run` wraps
the target in `c:\windows\system32\steam.exe`, which relaunches the exe and
exits — that breaks stdio inheritance, so the console launcher shows no prompts
and reads no input, and looks like it has hung.

```sh
GAME_ROOT="$HOME/.steam/steam/steamapps/common/Halo The Master Chief Collection"
BIN="$GAME_ROOT/MCC/Binaries/Win64"
PROTON="$HOME/.steam/steam/steamapps/common/Proton Hotfix/proton"

export STEAM_COMPAT_DATA_PATH="$HOME/.steam/steam/steamapps/compatdata/976730"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.steam/steam"
export HALOAP_NO_LAUNCH=1 HALOAP_NO_CONSOLE=1

# Once the launcher has installed the mod files, start MCC in the same prefix.
(
    until [ -f "$BIN/HaloAP.dll" ] && [ -f "$BIN/bink2w64_original.dll" ]; do sleep 1; done
    sleep 2
    cd "$BIN"
    SteamAppId=976730 SteamGameId=976730 \
        "$PROTON" runinprefix "$BIN/MCC-Win64-Shipping.exe" -no-eac
) &

cd /path/to/HaloAP
"$PROTON" runinprefix ./HaloAP_launcher.exe
```

Enter the room info at the prompts. Give the game directory as a wine path, e.g.
`Z:\home\you\.steam\steam\steamapps\common\Halo The Master Chief Collection`.

As on Windows, **do not close the launcher before quitting MCC** — it restores
`bink2w64.dll` on exit.

## Building on Linux

`build-launcher-clangcl.sh` and `build-dll-clangcl.sh` cross-build the launcher
and the mod DLL with `clang-cl` + [xwin](https://github.com/Jake-Shadle/xwin),
so no Visual Studio is needed. Install `clang`, `lld` and `xwin`, then:

```sh
xwin --accept-license splat --output ~/.xwin
./build-launcher-clangcl.sh
./build-dll-clangcl.sh
```

The proxy `bink2w64.dll` still needs MSVC: it forwards its exports with
`#pragma comment(linker, "/export:...")`, which clang-cl does not implement.
Use the one from the release.

Notes:

* The launcher must be built with the **static** CRT (`/MT`). Built `/MD` it
  imports `MSVCP140.dll`, and the msvcp140 present in a Proton prefix does not
  match what MSVC built it against — `std::mutex`'s `_Mtx_lock` receives a null
  pointer and the launcher dies with an access violation on its first
  `APClient::poll()`, before it can connect to the AP server. The `.vcxproj`
  now sets `<RuntimeLibrary>MultiThreaded</RuntimeLibrary>`, which also removes
  the VC++ redistributable requirement on Windows.
* `thirdparty/zlib` is referenced by the launcher `.vcxproj` but is not in the
  repository, so a fresh clone cannot build as-is. The build scripts define
  `WSWRAP_NO_COMPRESSION` to work around it; the AP server then warns that the
  client does not support compressed websocket connections.
* The scripts also define `WSWRAP_NO_SSL` (no OpenSSL import libraries), so a
  build made this way supports `ws://` only. Type the `ws://` prefix explicitly
  at the server prompt — without a scheme the launcher assumes `wss://`.
