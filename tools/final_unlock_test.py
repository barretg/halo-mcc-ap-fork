"""Final-mission unlock test, in all five games, with mocked mission completions.

Checks that each game's mission menu hides the right entry before the final unlocks and
shows (and starts) the right one after it unlocks. The DLL locks entries by their position
in the menu, so a menu entry out of step with the apworld's list shifts everything after
it. That's the bug behind "Lone Wolf never showed up" (Reach's Epilogue, m70_a, which is
before Lone Wolf in the menu and after it in the apworld).

The seed has every game, each with its default final (the last playable mission) and
every other mission required. Cutscene missions are left out (the default), or put in
with --cutscenes. Every Access item except the finals is sent, so the menus show
everything in the seed but the finals.

  1. locked:   for each game you open its mission list and say whether every mission
               except the final shows, and the final doesn't.
  2. unlock:   a second client on the slot checks every non-final completion location
               in one go (no playing). The launcher passes them on to the DLL.
  3. unlocked: for each game you reopen its list, see the final at the end, and start
               it. The harness checks the map that loads and passes or fails it by itself.

Typed here:  pass / p, fail <note> / f, skip, info, quit
Needs a fresh build/release (./build.sh). Run with Archipelago's venv python:
    ~/Projects/MoreProjects/Archipelago-src/.venv/bin/python tools/final_unlock_test.py [--cutscenes]

Results: build/final-unlock-test/results.txt. Logs: launcher.log, server.log there.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools/aptest"))

from ap_local import GAME, Server, generate, wait_for, websockets  # noqa: E402
import missions as mission_data  # noqa: E402

OUT = REPO / "build/final-unlock-test"
RESULTS = OUT / "results.txt"
RELEASE = REPO / "build/release/HaloAP-Linux"
PORT = 38993
SLOT = "FinalTest"

# Finals and required counts are left at their defaults: each game's last playable
# mission, needing every other one
YAML = f"""
name: {SLOT}
game: {GAME}
{GAME}:
  ce_enabled: true
  h2_enabled: true
  h3_enabled: true
  h4_enabled: true
  reach_enabled: true
  h2_cutscene_missions: {{cutscenes}}
  h3_cutscene_missions: {{cutscenes}}
  h4_cutscene_missions: {{cutscenes}}
  reach_cutscene_missions: {{cutscenes}}
  skullsanity: off
  death_link: false
"""

# Missions whose menu place differs from their apworld order (a sort key between numbers):
# Reach's Epilogue is listed after Lone Wolf (11) so Lone Wolf kept its IDs
MENU_POSITION = {("reach", "m70_a"): 10.5}


def say(text: str) -> None:
    for line in text.strip("\n").splitlines():
        print(f"\033[1;36m{line}\033[0m", flush=True)


class Step:
    def __init__(self, phase: str, game: str, title: str, steps: str, final_map: str = ""):
        self.phase, self.game, self.title, self.steps = phase, game, title, steps
        self.final_map = final_map  # unlocked steps: the map the final should load


class Test:
    def __init__(self, cutscenes: bool):
        OUT.mkdir(parents=True, exist_ok=True)
        # The missions in the seed, in menu order
        self.games = {
            game: sorted((m for m in missions if cutscenes or not m.cinematic),
                         key=lambda m: MENU_POSITION.get((m.game, m.map), m.number))
            for game, missions in mission_data.load().items()}
        self.lock = threading.RLock()
        self.step_index = -1
        self.steps: list[Step] = []
        self.unlocked = False
        self.required_sent: set[int] = set()   # game codes the DLL was sent a required count for

        # A server left over from an earlier run would answer in this one's place, with
        # its completions already checked
        if Server(Path(), PORT, SLOT, OUT / "server.log").connect() is not None:
            raise SystemExit(f"something is already serving port {PORT} (an earlier run's "
                             "MultiServer?); stop it first")
        print("== generating a seed")
        multidata = generate(OUT, YAML.format(cutscenes=str(cutscenes).lower()))
        (OUT / "server.log").unlink(missing_ok=True)
        self.server = Server(multidata, PORT, SLOT, OUT / "server.log")
        self.server.start()
        slot_data = self.server.connect()["slot_data"]
        self.finals = {}   # game key -> Mission
        for game, missions in self.games.items():
            # Matched by bare name, as the launcher does (slot data may use legacy CE names)
            bare = slot_data["final_missions"][game].split(": ", 1)[-1]
            bare = "Halo" if bare == "Halo (CE)" else bare
            self.finals[game] = next(m for m in missions if m.name == bare)
        for game, final in self.finals.items():
            print(f"   {mission_data.GAME_NAME[game]}: final {final.name} ({final.map}), "
                  f"needs {slot_data['missions_required'][game]}")

        for game, missions in self.games.items():
            for m in missions:
                if m is not self.finals[game]:
                    self.server.send_item(m.access)
        self.build_steps()

        script = RELEASE / "halo-ap.sh"
        if not script.exists():
            raise SystemExit(f"{script} not found; run ./build.sh first")
        print("== starting the game")
        self.log = open(OUT / "launcher.log", "w", encoding="utf-8")
        self.proc = subprocess.Popen(["bash", script], cwd=RELEASE,
                                     env=dict(os.environ, HALOAP_DEBUG="1"),
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                     errors="replace", bufsize=1)
        for line in (f"ws://127.0.0.1:{PORT}", SLOT, ""):
            self.write(line)
        threading.Thread(target=self.read, daemon=True).start()

    # ------------------------------------------------------------ the steps

    def build_steps(self) -> None:
        for game, missions in self.games.items():
            final = self.finals[game]
            name = mission_data.GAME_NAME[game]
            shown = [m.name for m in missions if m is not final]
            self.steps.append(Step("locked", game, f"{name}: the final is hidden", (
                f"Open {name}'s campaign mission list. It should show these {len(shown)}, "
                f"in this order, and nothing else:\n  " + "\n  ".join(shown) +
                f"\n{final.name} must NOT be there. (Extra or missing entries, or a cutscene "
                f"in its place, is a fail.) pass or fail <what you saw>.")))
        for game, missions in self.games.items():
            final = self.finals[game]
            name = mission_data.GAME_NAME[game]
            self.steps.append(Step("unlocked", game, f"{name}: the final shows and starts", (
                f"Back out and reopen {name}'s mission list. {final.name} should now be "
                f"there, right after {missions[missions.index(final) - 1].name}. "
                f"Start it: the harness checks that {final.map} loads. Then quit to the menu."),
                final_map=final.map))

    def step(self) -> Step | None:
        return self.steps[self.step_index] if 0 <= self.step_index < len(self.steps) else None

    def advance(self) -> None:
        self.step_index += 1
        s = self.step()
        if s is None:
            say("[final-test] All steps done. quit to finish.")
            return
        if s.phase == "unlocked" and not self.unlocked:
            # Off this thread: it waits on the launcher's output, which the reader thread
            # (possibly this one) delivers
            self.unlocked = True
            threading.Thread(target=self.unlock_then_show, args=(s,), daemon=True).start()
        else:
            self.show(s)

    def show(self, s: Step) -> None:
        say(f"\n[final-test] {self.step_index + 1}/{len(self.steps)} {s.title}")
        say(s.steps)

    def unlock_then_show(self, s: Step) -> None:
        self.unlock()
        self.show(s)

    def record(self, verdict: str, note: str = "") -> None:
        s = self.step()
        if s is None:
            return
        with RESULTS.open("a", encoding="utf-8") as f:
            f.write("|".join([time.strftime("%Y-%m-%d %H:%M:%S"), s.title, verdict,
                              note.replace("|", "/")]) + "\n")
        say(f"[final-test] Recorded {verdict}" + (f": {note}" if note else ""))
        self.advance()

    # ------------------------------------------------------------ the mock

    def unlock(self) -> None:
        """Checks every non-final completion, as a second client on the slot would"""
        ids = [m.completion for game, ms in self.games.items() for m in ms if m is not self.finals[game]]
        say(f"[final-test] Mocking {len(ids)} mission completions (every non-final mission)...")
        self.required_sent.clear()
        asyncio.run(self._check(ids))
        missing = set(ids) - self.server.checked()
        if missing:
            say(f"[final-test] The server didn't take {len(missing)} of them: {sorted(missing)}")
        codes = {mission_data.GAME_CODE[g] for g in self.games}
        if wait_for(lambda: codes <= self.required_sent, 20):
            say("[final-test] The launcher sent the new completion state to the DLL.")
        else:
            say("[final-test] The launcher didn't pass the completions on (no 'Sent game N "
                "missions required' for every game). Restart the launcher if the finals stay hidden.")

    async def _check(self, ids: list[int]) -> None:
        async with websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None) as ws:
            await ws.recv()  # RoomInfo
            await ws.send(json.dumps([{
                "cmd": "Connect", "game": GAME, "name": SLOT, "password": "", "uuid": "haloap-final-test",
                # The launcher's version: the apworld sets a minimum client version
                "version": {"major": 1, "minor": 2, "build": 0, "class": "Version"},
                "items_handling": 0, "tags": [], "slot_data": False}]))
            while True:
                packets = json.loads(await ws.recv())
                if any(p["cmd"] == "Connected" for p in packets):
                    break
                if any(p["cmd"] == "ConnectionRefused" for p in packets):
                    raise RuntimeError(packets)
            await ws.send(json.dumps([{"cmd": "LocationChecks", "locations": ids}]))
            await asyncio.sleep(1)

    # ------------------------------------------------------------ the launcher

    def write(self, line: str) -> None:
        try:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
        except OSError:
            pass

    def read(self) -> None:
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            self.log.write(line + "\n")
            self.log.flush()
            self.on_line(line)

    def on_line(self, line: str) -> None:
        with self.lock:
            if m := re.search(r"\[ap\] Sent game (\d+) missions required", line):
                self.required_sent.add(int(m.group(1)))
            elif line.startswith("DLL connected"):
                print(f"  {line}", flush=True)
                if self.step_index < 0:
                    say("[final-test] The DLL is connected. Wait for the main menu, then type next.")
            elif m := re.search(r"G_START:(\d+):(\S+)|MISSION_LOAD: path='[^']*\\(\w+)'", line):
                code, name = (int(m.group(1)), m.group(2)) if m.group(1) else (1, m.group(3))
                self.on_start(code, name)
            elif "is locked, ignoring" in line or "locked, quitting" in line or "error" in line.lower():
                print(f"  {line}", flush=True)

    def on_start(self, code: int, name: str) -> None:
        s = self.step()
        print(f"  [game] started {name}", flush=True)
        if s is None or s.phase != "unlocked" or mission_data.GAME_CODE[s.game] != code:
            if s is not None and s.phase == "locked" and name == self.finals[s.game].map:
                self.record("fail", f"the locked final {name} was started from the menu")
            return
        if name.lower() == s.final_map.lower():
            self.record("pass", f"{name} loaded")
        else:
            self.record("fail", f"started {name}, expected {s.final_map}")

    def command(self, verb: str, arg: str) -> bool:
        """One typed line; False to quit"""
        if verb in ("quit", "exit"):
            return False
        if verb in ("next", "n") and self.step_index < 0:
            self.advance()
        elif verb in ("pass", "p"):
            self.record("pass", arg)
        elif verb in ("fail", "f"):
            if arg:
                self.record("fail", arg)
            else:
                say("[final-test] fail needs a note.")
        elif verb == "skip":
            self.advance()
        elif verb == "info" and self.step():
            say(self.step().steps)
        elif verb:
            say("[final-test] next (to begin), pass, fail <note>, skip, info, quit")
        return True

    def close(self) -> None:
        try:
            self.proc.stdin.close()
            self.proc.wait(30)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.terminate()
        self.server.stop()


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cutscenes", action="store_true", help="put every game's cutscene missions in the seed")
    test = Test(parser.parse_args().cutscenes)
    try:
        for line in sys.stdin:
            verb, _, arg = line.strip().partition(" ")
            verb = verb.lower()
            with test.lock:
                if not test.command(verb, arg):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        print("== shutting down")
        test.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
