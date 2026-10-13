"""Check every chapter location against the mission scripts in the official editing kits.

For each chapter in the tables, this finds the script call that shows its card and follows
the scripts that start it back to mission start, keeping every condition on the way. A
chapter is then one of:

  ok           shown on every playthrough
  conditional  shown only under a difficulty, co-op or random check
  skippable    shown inside a cutscene the player can skip
  never        no running script shows it (a cut title, or a script that's commented out)

Checks on the insertion point aren't counted: they only skip a card when the mission is
started from a later checkpoint. It also lists chapter cards the scripts do show that have no location. Chapters the tables
send some other way (when the mission loads, or at the cutscene's mission segment) and
chapters removed as locations are marked as such and not counted.

    python tools/chapter_audit.py [--game ce|h2a|h3|h4|reach] [--kits <dir>] [-v]

Halo 4 only runs when asked for (--game h4); see the caveats below.

The kits (HCEEK, H2EK, H3EK, H4EK, HREK) are read from their .7z archives in the Steam
library; the scripts and scenario tags this needs are extracted once into
~/.cache/haloap/kits. -v also prints the script path to each card.

Caveats: Halo 4's kit scripts predate the shipped build (see
Docs/hook-map-h2-h3-h4-reach.md), so its results are a guide only. Scripts started by
something other than a script (a cinematic tag, an AI command list) look unreachable here.
"""
from __future__ import annotations

import argparse
import ast
import re
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STEAM = Path("/games/SteamLibrary/steamapps/common")
CACHE = Path.home() / ".cache/haloap/kits"
MCC = STEAM / "Halo The Master Chief Collection"

sys.path.insert(0, str(REPO / "tools"))


# --- reading the kits ---------------------------------------------------------------

KITS = {"ce": "HCEEK", "h2a": "H2EK", "h3": "H3EK", "h4": "H4EK", "reach": "HREK"}
EXTRACT = ["*.hsc", "*/solo/*.scenario", "*chapter_titles*"]


def kit_dir(game: str, root: Path) -> Path:
    kit = KITS[game]
    out = root / kit
    if not (out / ".extracted").exists():
        archive = STEAM / kit / f"{kit}.7z"
        if not archive.exists():
            sys.exit(f"{archive} not found; install {kit} from Steam (Halo MCC mod tools)")
        print(f"extracting {kit} scripts and scenarios into {out} (once)...", file=sys.stderr)
        subprocess.run(["7z", "x", "-y", "-bso0", "-bsp0", str(archive), f"-o{out}", "-r", *EXTRACT],
                       check=True)
        (out / ".extracted").touch()
    return out


# --- a script graph, from either syntax ---------------------------------------------

@dataclass
class Ref:
    name: str            # script or function referenced
    guards: tuple        # condition texts in force at the reference ("!x" = x is false)
    args: list           # plain identifier arguments, for title calls
    line: int


@dataclass
class Script:
    name: str
    kind: str            # startup, continuous, dormant, static, stub, command_script...
    params: list
    refs: list = field(default_factory=list)
    where: str = ""


def strip_lisp_comments(text: str) -> str:
    """Blank out ;* ... *; and ; comments, keeping line numbers and strings."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = text.find('"', i + 1)
            j = n if j < 0 else j + 1
            out.append(text[i:j]); i = j
        elif text.startswith(";*", i):
            j = text.find("*;", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j])); i = j
        elif c == ";":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i)); i = j
        else:
            out.append(c); i += 1
    return "".join(out)


TOKEN = re.compile(r'"[^"]*"|[()]|[^\s()"]+')


def parse_lisp(text: str):
    """Top-level forms as nested lists; atoms are (text, line)."""
    text = strip_lisp_comments(text)
    stack, top = [[]], None
    line_starts = [m.start() for m in re.finditer(r"\n", text)]
    import bisect
    for m in TOKEN.finditer(text):
        t = m.group()
        if t == "(":
            stack.append([])
        elif t == ")":
            if len(stack) > 1:
                done = stack.pop()
                stack[-1].append(done)
        else:
            stack[-1].append((t, bisect.bisect(line_starts, m.start()) + 1))
    return stack[0]


def atom(x):
    return x[0] if isinstance(x, tuple) else None


def show(x) -> str:
    if isinstance(x, tuple):
        return x[0]
    return "(" + " ".join(show(y) for y in x) + ")"


def lisp_scripts(forms, where: str) -> dict[str, Script]:
    out = {}
    for f in forms:
        if not isinstance(f, list) or len(f) < 3 or atom(f[0]) != "script":
            continue
        kind = atom(f[1]) or "?"
        rest = f[2:]
        # (script static <type> name ...) / (script static <type> (name (type p) ...) ...)
        if kind in ("static", "stub") and len(rest) >= 2:
            rest = rest[1:]
        head = rest[0]
        if isinstance(head, list):
            name = atom(head[0]); params = [atom(p[1]) for p in head[1:] if isinstance(p, list) and len(p) > 1]
        else:
            name = atom(head); params = []
        if not name:
            continue
        s = Script(name, kind, params, where=where)
        for body in rest[1:]:
            walk_lisp(body, (), s)
        out[name] = s
    return out


def walk_lisp(x, guards, s: Script):
    if isinstance(x, tuple):
        s.refs.append(Ref(x[0], guards, [], x[1]))
        return
    if not x:
        return
    fn = atom(x[0])
    args = x[1:]
    if fn == "if" and args:
        test = show(args[0])
        walk_lisp(args[0], guards, s)
        if len(args) > 1:
            walk_lisp(args[1], guards + (test,), s)
        for a in args[2:]:
            walk_lisp(a, guards + ("!" + test,), s)
        return
    if fn == "cond":
        prior = ()
        for clause in args:
            if isinstance(clause, list) and clause:
                test = show(clause[0])
                g = guards + prior + (() if test == "true" else (test,))
                walk_lisp(clause[0], guards + prior, s)
                for a in clause[1:]:
                    walk_lisp(a, g, s)
                prior += ("!" + test,)
        return
    if fn:
        s.refs.append(Ref(fn, guards, [atom(a) for a in args], x[0][1]))
    for a in (args if fn else x):
        walk_lisp(a, guards, s)


C_SCRIPT = re.compile(r"^\s*script\s+(\w+)\s+(?:(\w+)\s+)?(\w+)\s*\(([^)]*)\)", re.M)
C_IDENT = re.compile(r"\b([A-Za-z_]\w*)\s*(\()?")


def c_scripts(text: str, where: str) -> dict[str, Script]:
    """Halo 4's C-like syntax: script <kind> [type] name(params) ... end"""
    text = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group()), text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    out = {}
    lines = text.split("\n")
    cur, guards = None, []
    for no, raw in enumerate(lines, 1):
        line = raw.strip()
        m = C_SCRIPT.match(raw)
        if m:
            kind, a, b, params = m.groups()
            name = b
            ps = [p.split()[-1] for p in params.split(",") if p.strip()]
            cur = Script(name, kind, ps, where=where)
            out.setdefault(name, cur)
            if name in out and out[name] is not cur:   # overloads: merge
                cur = out[name]
            guards = []
            continue
        if cur is None:
            continue
        mi = re.match(r"(else)?if\s*\((.*)\)\s*then\b(.*)$", line)
        if line == "end" or line.startswith("end "):
            if guards:
                guards.pop()
            else:
                cur = None
            continue
        if mi:
            test = mi.group(2).strip()
            if mi.group(1):
                prev = guards.pop() if guards else ""
                guards.append(f"!{prev} & {test}")
            else:
                guards.append(test)
            body = mi.group(3)
            if body.strip().endswith("end"):     # one-line if ... then ... end
                for name, call in C_IDENT.findall(body):
                    cur.refs.append(Ref(name, tuple(guards), [], no))
                guards.pop()
            for name, call in C_IDENT.findall(test):
                cur.refs.append(Ref(name, tuple(guards[:-1]), [], no))
            continue
        if line == "else":
            if guards:
                guards[-1] = "!" + guards[-1]
            continue
        for m2 in re.finditer(r"\b([A-Za-z_]\w*)\s*\(\s*([A-Za-z_]\w*)?", line):
            cur.refs.append(Ref(m2.group(1), tuple(guards), [m2.group(2)], no))
        for name in re.findall(r"\b([A-Za-z_]\w*)\b", line):
            cur.refs.append(Ref(name, tuple(guards), [], no))
    return out


def embedded_sources(scenario: Path) -> list[str]:
    """Script source compiled into a scenario tag (H2/H3/Reach keep a copy of every source file)."""
    data = scenario.read_bytes()
    return [m.group().decode("latin-1") for m in re.finditer(rb"[\t\n\r\x20-\x7e]{20,}", data)
            if b"(script " in m.group()]


# --- title blocks --------------------------------------------------------------------

def isgt_block(path: Path, want: set[str]) -> list[str]:
    """The cutscene title names in block order (H3/H4/Reach tag format)."""
    data = path.read_bytes()
    entries = []
    for m in re.finditer(rb"isgt\x00\x00\x00\x00(.{4})", data, re.S):
        n = struct.unpack("<I", m.group(1))[0]
        if 0 < n < 64:
            name = data[m.end():m.end() + n]
            if re.fullmatch(rb"[A-Za-z0-9_]+", name):
                entries.append((m.start(), m.end() + n, name.decode()))
    clusters, cur = [], []
    for e in entries:
        if cur and e[0] - cur[-1][1] > 16:
            clusters.append(cur); cur = []
        cur.append(e)
    if cur:
        clusters.append(cur)
    best = max(clusters, key=lambda c: len({x[2] for x in c} & want), default=[])
    return [x[2] for x in best] if best and {x[2] for x in best} & want else []


def h2_block(path: Path) -> list[str]:
    """H2 tags: a dfbt block of 0x24-byte titles (name length first), then the names."""
    data = path.read_bytes()
    end = data.find(b"ui\\chapter_titles")
    for m in re.finditer(rb"dfbt\x00\x00\x00\x00(.{4})\x24\x00\x00\x00", data, re.S):
        count = struct.unpack("<I", m.group(1))[0]
        start = m.end()
        if not 0 < count < 64:
            continue
        lens = [data[start + i * 0x24 + 3] for i in range(count)]
        names_at = start + count * 0x24
        if names_at + sum(lens) == end:
            out, p = [], names_at
            for n in lens:
                out.append(data[p:p + n].decode()); p += n
            return out
    return []


# --- the tables ----------------------------------------------------------------------

def table(game: str):
    """[(mission name, map, [(chapter name, keys, how)])] from missions.py / chapter_map.h.
    how: "removed" (no longer a location), "on load" / "at its cutscene" (sent even when the
    card is missed), or "" (sent when the card shows)."""
    if game == "ce":
        from gen_mission_tables import CE, CE_ON_LOAD
        text = (REPO / "HaloAP_launcher/Data/chapter_map.h").read_text(encoding="utf-8-sig")
        segments = text[text.index("GetSegmentChapterMap"):]
        by_segment = {int(i) for i in re.findall(r'\{\s*"\w+:\w+",\s*\{\s*(\d+),', segments)}
        text = text[:text.index("GetSegmentChapterMap")]
        chapters: dict[str, dict[str, list]] = {}
        ids: dict[str, int] = {}
        for m, i, loc, name in re.findall(r'"(\w+):(\d+)",\s*\{\s*(\d+),\s*"([^"]*)"', text):
            chapters.setdefault(m, {}).setdefault(name, []).append(int(i))
            ids[name] = int(loc)
        out = []
        for n, code in CE:
            chs = []
            for cname, keys in chapters.get(code, {}).items():
                how = ("on load" if ids[cname] in CE_ON_LOAD.get(code, ())
                       else "at its cutscene" if ids[cname] in by_segment else "")
                chs.append((cname, keys, how))
            out.append((n, code, chs))
        return out
    src = (REPO / "apworld/halo_mcc/data/missions.py").read_text()
    tree = ast.parse(src)
    var = {"h2a": "H2_MISSIONS", "h3": "H3_MISSIONS", "h4": "H4_MISSIONS", "reach": "REACH_MISSIONS"}[game]
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if getattr(target, "id", None) == var:
                out = []
                for call in node.value.elts:
                    name, map_ = ast.literal_eval(call.args[0]), ast.literal_eval(call.args[1])
                    chs = []
                    if len(call.args) > 2:
                        for c in call.args[2].elts:
                            cname, key = ast.literal_eval(c.args[0]), ast.literal_eval(c.args[1])
                            flags = {k.arg for k in c.keywords if ast.literal_eval(k.value)}
                            how = "removed" if "unused" in flags else "on load" if "on_load" in flags else ""
                            chs.append((cname, list(key) if isinstance(key, tuple) else [key], how))
                    out.append((name, map_, chs))
                return out
    raise SystemExit(f"{var} not found in missions.py")


# --- per game --------------------------------------------------------------------------

@dataclass
class Level:
    scripts: dict
    block: list          # title names by index (empty for Reach: keys are names)
    texts: dict          # title name -> on-screen text, where known


TITLE_FNS = {"ce": {"cinematic_set_title"}, "h2a": {"cinematic_set_title"},
             "h3": {"cinematic_set_title"}, "h4": {"cinematic_set_title"},
             "reach": {"chud_show_screen_chapter_title"}}


def load_level(game: str, kit: Path, map_: str) -> Level:
    scripts: dict[str, Script] = {}

    def add_lisp(text, where):
        for name, s in lisp_scripts(parse_lisp(text), where).items():
            scripts[name] = s

    if game == "h4":
        level = kit / "tags/environments/solo" / map_
        files = sorted((kit / "tags/globals").rglob("*.hsc")) + sorted((level / "scripts").glob("*.hsc"))
        for f in files:
            for name, s in c_scripts(f.read_text(errors="replace"), str(f.relative_to(kit))).items():
                if name in scripts:
                    scripts[name].refs += s.refs
                else:
                    scripts[name] = s
        want = {a for s in scripts.values() for r in s.refs if r.name in ("f_chapter_title", "cinematic_set_title")
                for a in r.args if a}
        block = []
        for scn in sorted(level.glob("*.scenario")):
            block = isgt_block(scn, want)
            if block:
                break
        return Level(scripts, block, {})

    if game == "ce":
        globals_ = [kit / "data/global_scripts.hsc"]
        level = kit / "data/levels" / map_ / "scripts"
    elif game == "h2a":
        globals_ = sorted((kit / "data/globals").glob("*.hsc"))
        level = kit / "data/scenarios/solo" / map_ / "scripts"
    else:
        globals_ = sorted((kit / "data/globals").glob("*.hsc"))
        level = kit / "data/levels/solo" / map_ / "scripts"
    for f in globals_ + sorted(level.glob("*.hsc")):
        add_lisp(f.read_text(errors="replace"), str(f.relative_to(kit)))

    block, texts = [], {}
    if game == "ce":
        from ce_chapter_titles import Map
        titles = Map(MCC / "halo1/maps" / f"{map_}.map").titles()
        block = [n for n, _ in titles]
        texts = dict(titles)
    elif game in ("h2a", "h3", "reach"):
        sub = "scenarios/solo" if game == "h2a" else "levels/solo"
        scn = kit / "tags" / sub / map_ / f"{map_}.scenario"
        if scn.exists():
            # the copy of the source in the tag is what was compiled; it wins over the .hsc files
            for text in embedded_sources(scn):
                add_lisp(text, f"{scn.relative_to(kit)} (embedded source)")
            if game == "h2a":
                block = h2_block(scn)
            elif game == "h3":
                want = {a for s in scripts.values() for r in s.refs if r.name == "cinematic_set_title"
                        for a in r.args if a}
                block = isgt_block(scn, want)
    return Level(scripts, block, texts)


ROOT_KINDS = {"startup", "continuous"}
RISK = [("skippable", re.compile(r"cinematic_skip_start")),
        ("difficulty", re.compile(r"difficulty")),
        ("co-op", re.compile(r"cooperative|\bcoop")),
        ("random", re.compile(r"random")),
        ("debug", re.compile(r"\bdebug\b|editor_mode|b_debug"))]


def risks(guards) -> list[str]:
    out = []
    for g in guards:
        for label, rx in RISK:
            if rx.search(g):
                # "not debugging" is normal play
                if label == "debug" and (g.startswith("!") or g.startswith("(not ")):
                    break
                out.append(f"{label}: {g}")
                break
    return out


def reach(level: Level, game: str):
    """For each title name shown, the least-guarded path from mission start."""
    scripts = level.scripts
    # wrappers: scripts that show a title passed as a parameter, by parameter index
    wrappers = {fn: 0 for fn in TITLE_FNS[game]}
    changed = True
    while changed:
        changed = False
        for s in scripts.values():
            if s.name in wrappers:
                continue
            for r in s.refs:
                if r.name in wrappers and r.args and len(r.args) > wrappers[r.name]:
                    a = r.args[wrappers[r.name]]
                    if a in s.params:
                        wrappers[s.name] = s.params.index(a); changed = True
                        break

    # best path to each script: fewest risky guards, then shortest
    import heapq
    best: dict[str, tuple] = {}
    heap = [(0, 0, name, ()) for name, s in scripts.items() if s.kind in ROOT_KINDS]
    heapq.heapify(heap)
    while heap:
        nrisk, length, name, path = heapq.heappop(heap)
        if name in best:
            continue
        best[name] = (nrisk, path)
        for r in scripts[name].refs:
            if r.name in scripts and r.name not in best and r.name != name:
                step = path + ((name, r.guards, r.line),)
                heapq.heappush(heap, (nrisk + len(risks(r.guards)), length + 1, r.name, step))

    shown: dict[str, list] = {}
    for name, (nrisk, path) in best.items():
        s = scripts[name]
        for r in s.refs:
            if r.name in wrappers and not (r.name in scripts and s.name == r.name):
                i = wrappers[r.name]
                if len(r.args) > i and r.args[i] and r.args[i] not in s.params:
                    full = path + ((name, r.guards, r.line),)
                    flags = [f for _, g, _ in full for f in risks(g)]
                    shown.setdefault(r.args[i], []).append((flags, full))
    for v in shown.values():
        v.sort(key=lambda x: len(x[0]))
    # titles referenced by scripts nothing starts (for "never" explanations)
    dead = {}
    for s in scripts.values():
        if s.name not in best:
            for r in s.refs:
                if r.name in wrappers:
                    i = wrappers[r.name]
                    if len(r.args) > i and r.args[i]:
                        dead.setdefault(r.args[i], s.name)
    return shown, dead


def covers(guard_sets: list[list[str]]) -> bool:
    """True when the guard sets together hold in every case, e.g. a card per difficulty:
    [legendary], [!legendary, heroic], [!legendary, !heroic]."""
    if any(not g for g in guard_sets):
        return True
    if not guard_sets:
        return False
    g = guard_sets[0][0]
    pos, neg = g.lstrip("!"), "!" + g.lstrip("!")
    yes = [[x for x in gs if x != pos] for gs in guard_sets if neg not in gs]
    no = [[x for x in gs if x != neg] for gs in guard_sets if pos not in gs]
    if len(yes) == len(guard_sets) and len(no) == len(guard_sets) and all(pos not in gs for gs in yes):
        return False                     # the first guard is in no set; avoid looping
    return covers(yes) and covers(no)


def verdict(paths) -> tuple[str, list]:
    if not paths:
        return "never", []
    if covers([[f.split(": ", 1)[1] for f in flags] for flags, _ in paths]):
        return "ok", []
    if not paths[0][0]:
        return "ok", []
    if all(f.startswith("debug") for f in paths[0][0]):
        return "never", ["only when debugging"]
    if any(f.startswith("skippable") for f in paths[0][0]):
        return "skippable", paths[0][0]
    return "conditional", paths[0][0]


def fmt_path(full) -> str:
    return " -> ".join(f"{name}:{line}" for name, _, line in full)


def run(game: str, kits: Path, verbose: bool) -> int:
    kit = kit_dir(game, kits)
    problems = 0
    for mission, map_, chapters in table(game):
        level = load_level(game, kit, map_)
        shown, dead = reach(level, game)
        lines = []
        mapped = set()
        for cname, keys, how in chapters:
            names = []
            for k in keys:
                if isinstance(k, str):
                    names.append(k)
                elif 0 <= k < len(level.block):
                    names.append(level.block[k])
                else:
                    names.append(f"<index {k} not in block>")
            mapped.update(names)
            paths = [p for n in names for p in shown.get(n, [])]
            paths.sort(key=lambda x: len(x[0]))
            v, why = verdict(paths)
            if how == "removed":
                if v == "never":
                    lines.append(f"  removed     {cname} (not a location; older seeds get it on load)")
                    continue
                problems += 1
                why = ["marked unused, but a script shows it"] + why
            elif v != "ok" and how:
                v = f"{v}, sent {how}"
            elif v != "ok":
                problems += 1
            keytxt = ", ".join(f"{k}={n}" if not isinstance(k, str) else k for k, n in zip(keys, names))
            extra = ""
            if v == "never" and why:
                extra = f"  ({why[0]})"
            elif v == "never":
                where = [dead[n] for n in names if n in dead]
                extra = f"  (only in {', '.join(where)}, which nothing starts)" if where else "  (no script shows it)"
            elif why:
                extra = "  [" + "; ".join(why) + "]"
            lines.append(f"  {v:11} {cname} ({keytxt}){extra}")
            if how == "removed":
                lines[-1] = f"  !! {v} {cname} ({keytxt}){extra}"
            if verbose and paths:
                lines.append(f"              via {fmt_path(paths[0][1])}")
        # cards the scripts show that no location covers
        mapped_scripts = {p[1][-1][0] for n in mapped for p in shown.get(n, [])}
        for n, paths in sorted(shown.items()):
            if not n or n == '""' or n in mapped or n.startswith(("obj", "ct_obj", "ct_tutorial", "ct_objective")):
                continue
            if all(p[1][-1][0] in mapped_scripts for p in paths):
                continue                 # a later part of a mapped card, shown by the same script
            if level.texts.get(n, "").startswith((">", "[")):
                continue                 # CE 343 Guilty Spark's recording overlay, not a chapter
            if game == "h4" and not n.startswith("chapter_title"):
                continue
            if game in ("h2a", "h3") and not n.startswith("title"):
                continue
            v, why = verdict(paths)
            if v == "never":
                continue
            idx = level.block.index(n) if n in level.block else None
            text = level.texts.get(n, "")
            lines.append(f"  unmapped    {n}" + (f" (index {idx})" if idx is not None else "")
                         + (f" {text!r}" if text else "") + (f"  [{'; '.join(why)}]" if why else ""))
        if game != "reach" and chapters and not level.block:
            lines.append("  !! couldn't read the title block; indices unchecked")
        print(f"== {game} {mission} ({map_})")
        print("\n".join(lines) if lines else "  (no chapters)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", choices=list(KITS), action="append")
    ap.add_argument("--kits", type=Path, default=CACHE)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    total = 0
    for g in a.game or [g for g in KITS if g != "h4"]:
        if g == "h4":
            print("!! Halo 4's kit scripts differ from the shipped build: chapters live-verified in game\n"
                  "!! (Infinity, Composer) show as never here. Treat these results as a guide only.\n")
        total += run(g, a.kits, a.verbose)
    print(f"\n{total} chapters a player can miss that nothing else sends")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
