"""A local Archipelago for tests: generate a seed from this repo's apworld, host it, and
look at the slot from outside. Used by tools/launcher_test.py and tools/aptest.

Archipelago comes from $AP_DIR (default ~/Projects/MoreProjects/Archipelago-src), with
halo_mcc linked into its worlds/. Run the tools with its venv's python (they need
websockets).
"""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

AP_DIR = Path(os.environ.get("AP_DIR", Path.home() / "Projects/MoreProjects/Archipelago-src"))
AP_PYTHON = AP_DIR / ".venv/bin/python"
GAME = "Halo The Master Chief Collection"

try:
    import websockets
except ImportError:
    # Run with another python (e.g. the system one): start again with Archipelago's
    if AP_PYTHON.exists() and not os.environ.get("HALOAP_REEXEC"):
        os.environ["HALOAP_REEXEC"] = "1"
        os.execv(AP_PYTHON, [str(AP_PYTHON), *sys.argv])
    raise SystemExit(f"websockets isn't installed; run this with {AP_PYTHON} (set AP_DIR if "
                     "Archipelago is elsewhere)")


def wait_for(pred, timeout: float) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.25)
    return False


def generate(out: Path, yaml: str, seed: int = 1) -> Path:
    """Generates one seed from `yaml` into out/gen; returns the multidata zip."""
    gen = out / "gen"
    shutil.rmtree(gen, ignore_errors=True)
    (gen / "players").mkdir(parents=True)
    (gen / "players/player.yaml").write_text(yaml)
    subprocess.run([AP_PYTHON, "Generate.py", "--player_files_path", gen / "players",
                    "--outputpath", gen, "--seed", str(seed)],
                   cwd=AP_DIR, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return next(gen.glob("*.zip"))


def item_ids() -> dict[str, int]:
    """Item name -> id, from the apworld"""
    out = subprocess.run(
        [AP_PYTHON, "-c", "import json, worlds; from worlds.AutoWorld import AutoWorldRegister as R;"
         f"print(json.dumps(R.world_types[{GAME!r}].item_name_to_id))"],
        cwd=AP_DIR, capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


class Server:
    """MultiServer on 127.0.0.1:port; its console takes commands like /send."""

    def __init__(self, multidata: Path, port: int, slot: str, log: Path):
        self.multidata, self.port, self.slot, self.log = multidata, port, slot, log
        self.proc = None

    def start(self) -> None:
        log = open(self.log, "a")
        self.proc = subprocess.Popen(
            [AP_PYTHON, "MultiServer.py", "--port", str(self.port), "--host", "127.0.0.1", self.multidata],
            cwd=AP_DIR, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, text=True)
        if not wait_for(lambda: self.connect() is not None, 60):
            raise RuntimeError(f"the server didn't come up; see {self.log}")

    def stop(self) -> None:
        if self.proc:
            self.proc.terminate()
            self.proc.wait(10)
            self.proc = None

    def command(self, line: str) -> None:
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def send_item(self, item: str) -> None:
        self.command(f"/send {self.slot} {item}")

    async def _connect(self):
        async with websockets.connect(f"ws://127.0.0.1:{self.port}", max_size=None, open_timeout=3) as ws:
            await ws.recv()  # RoomInfo
            await ws.send(json.dumps([{
                "cmd": "Connect", "game": "", "name": self.slot, "password": "", "uuid": "haloap-test",
                "version": {"major": 0, "minor": 6, "build": 8, "class": "Version"},
                "items_handling": 0, "tags": ["TextOnly"], "slot_data": True,
            }]))
            while True:
                for packet in json.loads(await ws.recv()):
                    if packet["cmd"] == "Connected":
                        return packet
                    if packet["cmd"] == "ConnectionRefused":
                        raise RuntimeError(packet)

    def connect(self):
        """The slot's Connected packet (checked locations, slot data), or None."""
        try:
            return asyncio.run(self._connect())
        except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException):
            return None

    def checked(self) -> set[int]:
        packet = self.connect()
        return set(packet["checked_locations"]) if packet else set()
