"""Launcher tests without the game.

Generates a seed from the apworld in this repo, hosts it on a local Archipelago server,
runs the launcher in test mode (HALOAP_TEST: no game directory, no mod files, no MCC
launch) under Wine, and plays the DLL's part with tools/fake_dll: each test sends the
messages the hooks would send and checks which locations reach the server.

    <Archipelago>/.venv/bin/python tools/launcher_test.py [-k name]

Archipelago: see tools/ap_local.py. Everything else goes in build/test/. Needs wine,
clang-cl and the xwin SDK (see build-launcher-clangcl.sh).
"""
import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from ap_local import GAME, Server, generate, item_ids, wait_for

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "build/test"
WINEPREFIX = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "haloap/test-wineprefix"
PORT = 38991
SLOT = "Tester"
SERVER: Server

YAML = f"""
name: {SLOT}
game: {GAME}
{GAME}:
  ce_enabled: true
  h2_enabled: true
  h3_enabled: true
  h4_enabled: false
  reach_enabled: false
  skullsanity: off
  h3_skull_pickups: true
"""


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def newer(target: Path, sources) -> bool:
    return target.exists() and all(target.stat().st_mtime >= s.stat().st_mtime for s in sources)


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    launcher = OUT / "launcher/HaloAP_launcher.exe"
    sources = [*(REPO / "HaloAP_launcher").glob("*.cpp"), *(REPO / "HaloAP_launcher").glob("*.h"),
               *(REPO / "HaloAP_launcher/Data").glob("*.h"), REPO / "HaloAP_Shared/shared/common.h"]
    if not newer(launcher, sources):
        print("== building the launcher (ws:// only)")
        env = {k: v for k, v in os.environ.items() if k != "OPENSSL_DIR"}
        subprocess.run([REPO / "build-launcher-clangcl.sh", OUT / "launcher"], env=env, check=True,
                       stdout=subprocess.DEVNULL)

    fake = OUT / "fake_dll.exe"
    src = REPO / "tools/fake_dll/fake_dll.cpp"
    if not newer(fake, [src, REPO / "HaloAP_Shared/shared/common.h"]):
        print("== building the fake DLL")
        x = Path(os.environ.get("XWIN_ROOT", Path.home() / ".xwin"))
        subprocess.run([
            "clang-cl", "--target=x86_64-pc-windows-msvc", "/std:c++17", "/EHsc", "/MT", "/O2",
            "/nologo", "-fuse-ld=lld", f"-I{REPO / 'HaloAP_Shared'}",
            "/imsvc", x / "crt/include", "/imsvc", x / "sdk/include/ucrt",
            "/imsvc", x / "sdk/include/um", "/imsvc", x / "sdk/include/shared",
            src, f"/Fo{OUT}/", f"/Fe{fake}", "/link", "/subsystem:console", "/machine:x64",
            f"/libpath:{x / 'crt/lib/x86_64'}", f"/libpath:{x / 'sdk/lib/ucrt/x86_64'}",
            f"/libpath:{x / 'sdk/lib/um/x86_64'}", "kernel32.lib",
        ], check=True)


def wine_env() -> dict:
    env = dict(os.environ)
    # Outside the repo: a prefix's dosdevices/z: links to /, and editors that follow
    # symlinks while indexing the workspace would crawl the whole filesystem through it
    env.update(WINEPREFIX=str(WINEPREFIX), WINEDEBUG="-all",
               WINEDLLOVERRIDES="mscoree,mshtml=", HALOAP_TEST="1", HALOAP_DEBUG="1")
    return env


def generate_seed() -> Path:
    print("== generating a seed")
    return generate(OUT, YAML)


def checked() -> set[int]:
    return SERVER.checked()


# ---------------------------------------------------------------------------
# Launcher + fake DLL
# ---------------------------------------------------------------------------

class Launcher:
    def __init__(self):
        env = wine_env()
        self.log = open(OUT / "launcher.log", "w")
        self.launcher = subprocess.Popen(
            ["wine", OUT / "launcher/HaloAP_launcher.exe"], cwd=OUT / "launcher", env=env,
            stdin=subprocess.PIPE, stdout=self.log, stderr=subprocess.STDOUT, text=True)
        self.launcher.stdin.write(f"ws://127.0.0.1:{PORT}\n{SLOT}\n\n")
        self.launcher.stdin.flush()

        self.received: list[str] = []
        self.dll = subprocess.Popen(
            ["wine", OUT / "fake_dll.exe"], cwd=OUT, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        threading.Thread(target=self._read, daemon=True).start()
        if not wait_for(lambda: "!! connected" in self.received, 60):
            raise RuntimeError("fake DLL never connected; see build/test/launcher.log")

    def _read(self) -> None:
        for line in self.dll.stdout:
            self.received.append(line.rstrip("\n"))

    def send(self, *messages: str) -> None:
        for m in messages:
            self.dll.stdin.write(m + "\n")
        self.dll.stdin.flush()

    def command(self, line: str) -> None:
        """Types a line into the launcher's console"""
        self.launcher.stdin.write(line + "\n")
        self.launcher.stdin.flush()

    def close(self) -> None:
        for p in (self.dll, self.launcher):
            try:
                p.stdin.close()
            except OSError:
                pass
        for p in (self.dll, self.launcher):
            try:
                p.wait(15)
            except subprocess.TimeoutExpired:
                p.kill()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class Ctx:
    def __init__(self, server: Server, launcher: Launcher, slot_data: dict, ids: dict[str, int]):
        self.server, self.launcher, self.slot_data, self.ids = server, launcher, slot_data, ids

    def give(self, item: str) -> None:
        self.server.send_item(item)
        wait_for(lambda: any(item_id_line(l, self.ids[item]) for l in self.launcher.received), 15)

    def expect(self, locations: set[int], timeout: float = 15) -> set[int]:
        """Locations still missing after the timeout."""
        wait_for(lambda: locations <= checked(), timeout)
        return locations - checked()

    def expect_not(self, locations: set[int], wait: float = 3) -> set[int]:
        time.sleep(wait)
        return locations & checked()


def item_id_line(line: str, item_id: int) -> bool:
    return line == f"<< ITEM_RECIVED: {item_id}"


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


@test
def ce_chapter_with_map(ctx: Ctx):
    """CHAPTER:<map>:<index> counts for that map, whatever the last MISSION_LOAD was"""
    ctx.launcher.send("MISSION_LOAD: path='levels\\a10\\a10'", "CHAPTER:a50:4")
    return ctx.expect({103013}) or ctx.expect_not({101012}, 0)


@test
def ce_chapter_old_format(ctx: Ctx):
    """CHAPTER:<index> from older DLLs uses the last MISSION_LOAD"""
    ctx.launcher.send("MISSION_LOAD: path='levels\\a30\\a30'", "CHAPTER:1")
    return ctx.expect({102012})


@test
def ce_win_sends_chapters(ctx: Ctx):
    """A CE win sends the mission and all its chapters"""
    ctx.launcher.send("MISSION_COMPLETE: c20")
    return ctx.expect({107000, 107011, 107012, 107013, 107014})


@test
def h3_locked_mission_ignored(ctx: Ctx):
    """Chapters of a locked mission don't count, and do once its Access arrives"""
    storm = 305000
    if ctx.slot_data["starting_missions"].get("h3") == "Halo 3: The Storm":
        return {"skipped: The Storm is the starting mission"}
    ctx.launcher.send("G_CHAPTER:3:040_voi:1")
    leaked = ctx.expect_not({305012})
    if leaked:
        return leaked
    ctx.give("Halo 3: The Storm Access")
    ctx.launcher.send("G_CHAPTER:3:040_voi:1")
    return ctx.expect({305012})


@test
def h3_win_sends_chapters(ctx: Ctx):
    """An H3 win sends the mission and all its chapters"""
    ctx.give("Halo 3: The Storm Access")
    ctx.launcher.send("G_COMPLETE:3:040_voi")
    return ctx.expect({305000, 305011, 305012, 305013})


@test
def h3_skull(ctx: Ctx):
    """An H3 skull pickup sends its location"""
    ctx.give("Halo 3: The Storm Access")
    ctx.launcher.send("G_SKULL:3:040_voi:3")
    return ctx.expect({305021})


@test
def h2_metropolis_difficulty_card(ctx: Ctx):
    """Each difficulty's first Metropolis card is the same chapter"""
    ctx.give("Halo 2: Metropolis Access")
    ctx.launcher.send("G_CHAPTER:2:03b_newmombasa:2")
    return ctx.expect({205011})


@test
def check_while_server_down(ctx: Ctx):
    """A check made while the server is down arrives once it's back"""
    ctx.give("Halo 3: Sierra 117 Access")
    ctx.server.stop()
    time.sleep(2)
    ctx.launcher.send("G_CHAPTER:3:010_jungle:0")
    time.sleep(2)
    ctx.server.start()
    return ctx.expect({302011}, timeout=30)


@test
def debug_commands_forwarded(ctx: Ctx):
    """With HALOAP_DEBUG, /title, /win and /deathlink typed in the launcher reach the DLL"""
    want = ["<< DEBUG: title 2", "<< DEBUG: win", "<< DEATHLINK: HaloAP debug"]
    for line in ("/title 2", "/win", "/deathlink"):
        ctx.launcher.command(line)
    wait_for(lambda: all(w in ctx.launcher.received for w in want), 10)
    return {w for w in want if w not in ctx.launcher.received}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", help="only tests whose name contains this")
    args = parser.parse_args()

    if not shutil.which("wine"):
        print("wine not found")
        return 1
    build()
    global SERVER
    multidata = generate_seed()
    (OUT / "server.log").unlink(missing_ok=True)
    server = SERVER = Server(multidata, PORT, SLOT, OUT / "server.log")
    server.start()
    slot_data = server.connect()["slot_data"]
    ids = item_ids()

    launcher = Launcher()
    failures = 0
    try:
        for fn in TESTS:
            if args.k and args.k not in fn.__name__:
                continue
            ctx = Ctx(server, launcher, slot_data, ids)
            try:
                problem = fn(ctx)
            except Exception as e:  # noqa: BLE001
                problem = {f"error: {e!r}"}
            if problem and all(isinstance(p, str) and p.startswith("skipped") for p in problem):
                print(f"SKIP {fn.__name__}: {next(iter(problem))}")
            elif problem:
                failures += 1
                print(f"FAIL {fn.__name__}: {fn.__doc__}\n     missing/wrong: {sorted(problem, key=str)}")
            else:
                print(f"ok   {fn.__name__}")
    finally:
        launcher.close()
        server.stop()
    print(f"\n{failures} failed. Logs: build/test/launcher.log, build/test/server.log")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
