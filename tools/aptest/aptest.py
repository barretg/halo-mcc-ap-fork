"""APTest: scenario-by-scenario play testing for MCC-AP.

Generates a seed with every game in it, hosts it locally, and starts the game through
build/release/HaloAP-Linux/halo-ap.sh with the launcher's console running through this
terminal (and HALOAP_DEBUG on). Each scenario names a mission; the harness sends its
Access item, gets the mission loaded, sends the scenario's debug commands (/title, /win)
once it's running, and reports the checks that arrive. You give the verdict here;
scenarios with nothing to look at pass or fail by themselves.

The harness says which mission to start from the menu. MCC's builds stub out the
games' own map-launch script functions (map_name, game_start), so nothing in a game can
load another mission; see Docs/testing.md.

Typed here:
    next               the next open scenario (no verdict yet, or failed in an earlier run)
    pass [note] / p    record a verdict; the next open scenario starts
    fail <note> / f    note <text>
    redo / prev / go <n> / info / status / list [text]
    groups / group <name>
    give <item>        send an item from the server
    clear [yes]        drop this group's verdicts (kept in results_cleared.txt)
    /<command>         to the launcher: /title <n>, /win, /hs <expr>, /deathlink
    quit

Usage (Archipelago's venv python, see tools/ap_local.py):
    python tools/aptest/aptest.py --list-groups
    python tools/aptest/aptest.py --group smoke
    python tools/aptest/aptest.py --group smoke --fake   # no game: a fake DLL acts it out

Results: build/aptest/results.txt. Logs: build/aptest/{launcher,server}.log.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import groups as group_registry  # noqa: E402
import missions as mission_data  # noqa: E402
from ap_local import Server, generate, item_ids, wait_for  # noqa: E402
from scenario import Context, Group, Scenario  # noqa: E402

OUT = REPO / "build/aptest"
RESULTS = OUT / "results.txt"
CLEARED = OUT / "results_cleared.txt"
PORT = 38992
SLOT = "APTest"
GAME = "Halo The Master Chief Collection"
RELEASE = REPO / "build/release/HaloAP-Linux"

# Every game, every final open from the start, skulls left alone
YAML = f"""
name: {SLOT}
game: {GAME}
{GAME}:
  ce_enabled: true
  h2_enabled: true
  h3_enabled: true
  h4_enabled: true
  reach_enabled: true
  ce_missions_required: 0
  h2_missions_required: 0
  h3_missions_required: 0
  h4_missions_required: 0
  reach_missions_required: 0
  skullsanity: off
  h2_skull_pickups: true
  h3_skull_pickups: true
  death_link: true
  death_link_amnesty: 0
"""

COMMAND_GAP = 4         # seconds between a scenario's commands


# -------------------------------------------------------------- the game


class Game:
    """The launcher (and, through halo-ap.sh, MCC) with its console piped through here.
    Calls on_line for every line the launcher prints."""

    def __init__(self, on_line, fake: bool):
        self.on_line = on_line
        self.log = open(OUT / "launcher.log", "w", encoding="utf-8")
        env = dict(os.environ, HALOAP_DEBUG="1")
        if fake:
            sys.path.insert(0, str(REPO / "tools"))
            import launcher_test as lt  # the fake DLL and test-mode launcher builds
            lt.build()
            env.update(lt.wine_env())
            cmd, cwd = ["wine", lt.OUT / "launcher/HaloAP_launcher.exe"], lt.OUT / "launcher"
        else:
            script = RELEASE / "halo-ap.sh"
            if not script.exists():
                raise SystemExit(f"{script} not found; run ./build.sh first")
            cmd, cwd = ["bash", script], RELEASE
        self.proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", bufsize=1)
        self.write(f"ws://127.0.0.1:{PORT}")
        self.write(SLOT)
        self.write("")
        threading.Thread(target=self._read, args=(self.proc.stdout,), daemon=True).start()
        self.fake = FakeMission(env, self.on_line) if fake else None

    def _read(self, stream) -> None:
        for line in stream:
            line = line.rstrip("\n")
            self.log.write(line + "\n")
            self.log.flush()
            self.on_line(line)

    def write(self, line: str) -> None:
        try:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
        except OSError:
            pass

    def close(self) -> None:
        if self.fake:
            self.fake.close()
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(30)
        except subprocess.TimeoutExpired:
            self.proc.terminate()


class FakeMission:
    """--fake: the fake DLL, acting out what the debug commands would do in game"""

    def __init__(self, env: dict, on_line):
        import launcher_test as lt
        self.map: tuple[int, str] | None = None
        self.proc = subprocess.Popen(["wine", lt.OUT / "fake_dll.exe"], cwd=lt.OUT, env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()

    def start(self, mission) -> None:
        """Stands in for starting a mission from the menu"""
        code = mission_data.GAME_CODE[mission.game]
        self.map = (code, mission.map)
        self.send(f"MISSION_LOAD: path='{mission.load_path}'" if code == 1 else f"G_START:{code}:{mission.map}")

    def send(self, msg: str) -> None:
        self.proc.stdin.write(msg + "\n")
        self.proc.stdin.flush()

    def _read(self) -> None:
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            if not line.startswith("<< DEBUG: "):
                continue
            cmd = line[len("<< DEBUG: "):]
            if not self.map:
                self.send("DEBUG_RESULT: not in a mission in time, dropped")
            elif cmd.startswith("title "):
                code, name = self.map
                n = cmd[6:]
                self.send(f"CHAPTER:{name}:{n}" if code == 1 else f"G_CHAPTER:{code}:{name}:{n}")
            elif cmd == "win":
                code, name = self.map
                self.send(f"MISSION_COMPLETE: {name}" if code == 1 else f"G_COMPLETE:{code}:{name}")
                self.map = None

    def close(self) -> None:
        try:
            self.proc.stdin.close()
            self.proc.wait(15)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()


# -------------------------------------------------------------- results


def read_results() -> list[list[str]]:
    if not RESULTS.exists():
        return []
    return [line.split("|") for line in RESULTS.read_text(encoding="utf-8").splitlines() if line]


def latest_verdicts() -> dict[tuple[str, str], str]:
    """{(group, title): verdict}, the last one per scenario winning"""
    return {(p[6], p[2]): p[3] for p in read_results() if len(p) >= 7}


# -------------------------------------------------------------- the harness


class Harness:
    def __init__(self, ctx: Context, groups: dict[str, Group], group: str, fake: bool):
        self.ctx = ctx
        self.groups = groups
        self.fake = fake
        self.lock = threading.RLock()
        self.group = ""
        self.scenarios: list[Scenario] = []
        self.current = -1
        self.failed_now: set[tuple[str, str]] = set()

        # Game state, from the launcher's console
        self.running: tuple[int, str] | None = None   # (game code, map) of the mission
        self.connected = False
        self.seen: set[int] = set()        # checks since the scenario started
        self.given: set[str] = set()       # items sent this session
        self.waiting_for_mission = False
        self.pending_commands: list[str] = []
        self.next_command_at = 0.0
        self.commands_done_at = 0.0

        OUT.mkdir(parents=True, exist_ok=True)
        print("== generating a seed")
        multidata = generate(OUT, YAML)
        (OUT / "server.log").unlink(missing_ok=True)
        self.server = Server(multidata, PORT, SLOT, OUT / "server.log")
        self.server.start()
        slot_data = self.server.connect()["slot_data"]
        self.starting = set(slot_data.get("starting_missions", {}).values())
        self.items = item_ids()
        self.location_names = {}
        for missions in ctx.games.values():
            for m in missions:
                self.location_names[m.completion] = f"{m.level} Complete"
                for c in m.chapters:
                    self.location_names[c.location] = f"{m.level} - {c.name}"
                for s in m.skulls:
                    self.location_names[s.location] = f"{m.level} - {s.name} Skull"
                if m.start_location:
                    self.location_names[m.start_location] = f"{m.level} - Mission Start"
        self.select(group)

        print("== starting the game" + (" (fake)" if fake else ""))
        self.game = Game(self.on_line, fake)
        threading.Thread(target=self.ticker, daemon=True).start()

    # Talking to the tester

    def tell(self, text: str) -> None:
        for line in text.strip("\n").splitlines():
            print(f"\033[1;36m{line}\033[0m" if line.startswith("[aptest]") else line, flush=True)

    # The launcher's console

    SHOWN = ("[ap] Chapter", "[ap] Skull", "[ap] game", "[ap] MISSION_COMPLETE", "[ap] Unknown",
             "[ap] *** ", "[deathlink]", "[ap] not connected", "[ap] resending", "DLL connected",
             "Could not connect", "halo-ap:", "Debug commands", "  /")

    def on_line(self, line: str) -> None:
        with self.lock:
            if line.startswith("[dll] DEBUG_RESULT: "):
                self.on_debug_result(line[len("[dll] DEBUG_RESULT: "):])
            elif line.startswith("[dll] MISSION_LOAD: "):
                m = re.search(r"levels\\(\w+)\\", line)
                if m:
                    self.on_mission(1, m.group(1))
            elif line.startswith("[dll] G_START:"):
                code, _, name = line[len("[dll] G_START:"):].partition(":")
                self.on_mission(int(code), name)
            elif line.startswith(("[dll] G_COMPLETE:", "[dll] MISSION_COMPLETE:")):
                self.running = None  # a win goes back to the menu
            elif (m := re.match(r"\[ap\] sent location check: (\d+)", line)) or \
                    (m := re.match(r"\[ap\] location (\d+) already sent this session", line)):
                self.on_check(int(m.group(1)), "already sent" in line)
            elif "*** slot connected ***" in line:
                self.connected = True
            elif line.startswith("DLL connected"):
                self.tell("[aptest] The DLL is connected. Type next to begin.")
            if line.startswith(self.SHOWN) or "error" in line.lower():
                print(f"  {line}", flush=True)

    def on_debug_result(self, text: str) -> None:
        self.tell(f"[aptest] DLL: {text}")

    def on_mission(self, code: int, name: str) -> None:
        self.running = (code, name)
        s = self.scenario()
        if s is None or not self.waiting_for_mission:
            return
        if (mission_data.GAME_CODE[s.mission.game], s.mission.map) == (code, name):
            self.waiting_for_mission = False
            self.tell(f"[aptest] {s.mission.level} is running.")
            self.pending_commands = list(s.commands)
            self.next_command_at = time.time() + 3
            if not s.commands:
                self.commands_done_at = time.time()
        else:
            self.tell(f"[aptest] That's {name}, not {s.mission.map} ({s.mission.level}).")

    def on_check(self, location: int, again: bool) -> None:
        s = self.scenario()
        name = self.location_names.get(location, str(location))
        new = location not in self.seen
        self.seen.add(location)
        if s is None or not new:
            return
        if location in s.expect:
            note = " (already sent earlier this session)" if again else ""
            self.tell(f"[aptest] Expected check: {name}{note}")
            if set(s.expect) <= self.seen:
                if s.auto:
                    self.tell("[aptest] Every expected check arrived.")
                    self.record("pass", "auto")
                else:
                    self.tell("[aptest] Every expected check arrived. pass or fail <what was wrong>.")
        elif not again:  # a repeat the launcher skipped (e.g. a card shown again) isn't news
            self.tell(f"[aptest] Unexpected check: {name}")

    def ticker(self) -> None:
        while True:
            time.sleep(1)
            with self.lock:
                now = time.time()
                if self.pending_commands and now >= self.next_command_at:
                    command = self.pending_commands.pop(0)
                    self.tell(f"[aptest] Sending {command}")
                    self.launcher(command)
                    self.next_command_at = now + COMMAND_GAP
                    if not self.pending_commands:
                        self.commands_done_at = now
                s = self.scenario()
                if s is not None and s.auto and self.commands_done_at and \
                        now - self.commands_done_at > s.timeout:
                    missing = [self.location_names.get(i, str(i)) for i in s.expect if i not in self.seen]
                    self.commands_done_at = 0
                    if missing:
                        self.record("fail", "auto: never arrived: " + ", ".join(missing))

    def launcher(self, command: str) -> None:
        self.game.write(command)

    # Missions

    def ask_manual_load(self) -> None:
        s = self.scenario()
        if s is not None and self.fake:
            self.game.fake.start(s.mission)
        elif s is not None:
            self.tell(f"[aptest] Start {s.mission.level} from the menu "
                      f"(map {s.mission.map}); the scenario carries on once it's running.")

    def load_mission(self) -> None:
        self.waiting_for_mission = True
        self.ask_manual_load()

    # Groups and scenarios

    def select(self, name: str) -> bool:
        if name not in self.groups:
            self.tell(f"[aptest] No group '{name}'. groups lists them.")
            return False
        self.group = name
        self.scenarios = group_registry.build(name, self.groups, self.ctx)
        self.current = -1
        return True

    def scenario(self) -> Scenario | None:
        return self.scenarios[self.current] if 0 <= self.current < len(self.scenarios) else None

    def start(self, index: int) -> None:
        if not 0 <= index < len(self.scenarios):
            self.tell(f"[aptest] No scenario {index}; there are {len(self.scenarios)}.")
            return
        s = self.scenarios[index]
        blocked = [lv for lv in s.locked if f"{lv} Access" in self.given or lv in self.starting]
        if blocked:
            self.tell(f"[aptest] {s.title} needs {', '.join(blocked)} locked, but it's unlocked "
                      "this session. Restart the harness to run it.")
            return
        self.current = index
        self.seen = set()
        self.pending_commands = []
        self.commands_done_at = 0
        self.tell(f"\n[aptest] {self.group} {index}/{len(self.scenarios) - 1}: {s.title}")
        wanted = list(s.give)
        if s.mission.level not in s.locked:
            wanted.append(s.mission.access)
        for item in wanted:
            self.give(item, quiet=True)
        self.info()
        code = mission_data.GAME_CODE[s.mission.game]
        if self.running == (code, s.mission.map) and not s.reload:
            self.waiting_for_mission = True
            self.on_mission(code, s.mission.map)
        else:
            self.load_mission()

    def give(self, item: str, quiet: bool = False) -> None:
        if item not in self.items:
            if not quiet:
                self.tell(f"[aptest] No item '{item}'.")
            return
        if item in self.given:
            return
        self.given.add(item)
        self.server.send_item(item)
        self.tell(f"[aptest] Sent {item}")

    def info(self) -> None:
        s = self.scenario()
        if s is None:
            self.tell("[aptest] No scenario running. next starts the first open one.")
            return
        steps = " ".join(line.strip() for line in s.steps.strip().splitlines())
        if steps:
            self.tell(steps)
        if s.expect:
            self.tell("Expects: " + ", ".join(self.location_names.get(i, str(i)) for i in s.expect))

    def next_open(self, after: int = -1) -> int | None:
        verdicts = latest_verdicts()
        count = len(self.scenarios)
        for step in range(1, count + 1):
            i = (after + step) % count
            if i == after:
                break
            key = (self.scenarios[i].origin, self.scenarios[i].title)
            verdict = verdicts.get(key)
            if verdict is None or (verdict == "fail" and key not in self.failed_now):
                return i
        return None

    def record(self, verdict: str, note: str) -> None:
        s = self.scenario()
        if s is None:
            self.tell("[aptest] No scenario running.")
            return
        seen = ",".join(str(i) for i in sorted(self.seen))
        line = "|".join([time.strftime("%Y-%m-%d %H:%M:%S"), str(self.current), s.title, verdict,
                         note.replace("|", "/"), seen, s.origin])
        with RESULTS.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        if verdict == "fail":
            self.failed_now.add((s.origin, s.title))
        self.tell(f"[aptest] Recorded {verdict}" + (f": {note}" if note else "") + ".")
        self.pending_commands = []
        self.commands_done_at = 0
        following = self.next_open(self.current)
        if following is None:
            self.current = -1
            self.tell("[aptest] No open scenarios left in this group.")
            self.status()
        else:
            self.start(following)

    def status(self) -> None:
        verdicts = latest_verdicts()
        counts: dict[str, int] = {}
        for s in self.scenarios:
            v = verdicts.get((s.origin, s.title), "untested")
            counts[v] = counts.get(v, 0) + 1
        self.tell(f"[aptest] {self.group}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))

    def list(self, text: str) -> None:
        verdicts = latest_verdicts()
        for i, s in enumerate(self.scenarios):
            if text.lower() in s.title.lower():
                mark = verdicts.get((s.origin, s.title), "")
                print(f"{i:4} {('[' + mark + '] ') if mark else ''}{s.title}")

    def clear(self, arg: str) -> None:
        if arg != "yes":
            self.tell(f"[aptest] This drops every '{self.group}' verdict. clear yes to go ahead.")
            return
        keys = {(s.origin, s.title) for s in self.scenarios}
        kept, dropped = [], []
        for p in read_results():
            (dropped if len(p) >= 7 and (p[6], p[2]) in keys else kept).append("|".join(p))
        with CLEARED.open("a", encoding="utf-8") as handle:
            handle.write("".join(line + "\n" for line in dropped))
        RESULTS.write_text("".join(line + "\n" for line in kept), encoding="utf-8")
        self.tell(f"[aptest] Cleared {len(dropped)} verdict(s).")

    def command(self, line: str) -> bool:
        """One typed line; False to quit"""
        line = line.strip()
        if not line:
            return True
        if line.startswith("/"):
            self.launcher(line)
            return True
        verb, _, arg = line.partition(" ")
        verb, arg = verb.lower(), arg.strip()
        with self.lock:
            if verb in ("pass", "p"):
                self.record("pass", arg)
            elif verb in ("fail", "f", "note"):
                if arg:
                    self.record("note" if verb == "note" else "fail", arg)
                else:
                    self.tell(f"[aptest] {verb} needs a note.")
            elif verb in ("next", "n"):
                following = self.next_open(self.current)
                if following is None:
                    self.tell("[aptest] No open scenarios. go <n> or list to pick one.")
                else:
                    self.start(following)
            elif verb == "prev":
                self.start(self.current - 1)
            elif verb == "redo":
                self.start(self.current)
            elif verb == "go" and arg.isdigit():
                self.start(int(arg))
            elif verb == "info":
                self.info()
            elif verb == "status":
                self.status()
            elif verb == "list":
                self.list(arg)
            elif verb == "groups":
                for name, g in self.groups.items():
                    self.tell(f"[aptest] {'*' if name == self.group else ' '} {name}: {g.summary}")
            elif verb == "group" and arg:
                if self.select(arg):
                    self.tell(f"[aptest] Now on '{self.group}' ({len(self.scenarios)} scenarios). next to begin.")
            elif verb == "give" and arg:
                self.give(arg)
            elif verb == "clear":
                self.clear(arg)
            elif verb in ("quit", "exit"):
                return False
            else:
                self.tell("[aptest] next, pass, fail <note>, note <text>, redo, prev, go <n>, info, "
                          "status, list, groups, group <name>, give <item>, clear, /<command>, quit")
        return True

    def close(self) -> None:
        self.game.close()
        self.server.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group", default="smoke")
    parser.add_argument("--list-groups", action="store_true")
    parser.add_argument("--fake", action="store_true", help="no game: a fake DLL acts the commands out")
    args = parser.parse_args()

    if args.fake:
        # Its own results, so a dry run doesn't mark anything tested
        global OUT, RESULTS, CLEARED
        OUT = REPO / "build/aptest-fake"
        RESULTS, CLEARED = OUT / "results.txt", OUT / "results_cleared.txt"

    ctx = Context(mission_data.load())
    groups = group_registry.discover()
    if args.list_groups:
        verdicts = latest_verdicts()
        for name, g in groups.items():
            scenarios = group_registry.build(name, groups, ctx)
            done = sum(1 for s in scenarios if verdicts.get((s.origin, s.title)) == "pass")
            print(f"{name:16} {done}/{len(scenarios)} passed  {g.summary}")
        return 0
    if args.group not in groups:
        print(f"No group '{args.group}'; --list-groups lists them.")
        return 1

    harness = Harness(ctx, groups, args.group, args.fake)
    try:
        for line in sys.stdin:
            if not harness.command(line):
                break
    except KeyboardInterrupt:
        pass
    finally:
        print("== shutting down")
        harness.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
