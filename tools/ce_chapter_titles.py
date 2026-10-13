"""Halo CE chapter titles, read from MCC's map files.

For each campaign map: every cutscene title (its index is what cinematic_set_title gets,
and so what the DLL's chapter hook reports), the text it shows, the scripts that show it,
and whether that happens inside a skippable cutscene, i.e. under
(if (cinematic_skip_start) ...) directly or through scripts called from there.

    python tools/ce_chapter_titles.py [<MCC>/halo1/maps] [--check]

--check compares the result with HaloAP_launcher/Data/chapter_map.h and exits 1 on a
mismatch.
"""
import re
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_MAPS = Path("/games/SteamLibrary/steamapps/common/Halo The Master Chief Collection/halo1/maps")
MAPS = ["a10", "a30", "a50", "b30", "b40", "c10", "c20", "c40", "d20", "d40"]

# Offsets in the scenario tag (CE, MCC map version 13)
SCNR_SYNTAX_DATA = 0x474
SCNR_STRING_DATA = 0x488
SCNR_SCRIPTS = 0x49C
SCNR_TITLES = 0x4FC
SCNR_HELP_TEXT = 0x584      # ustr dependency: the titles' text
TITLE_SIZE = 0x60           # name at +4, string index at +0x30
SCRIPT_SIZE = 0x5C          # name at +0, root expression id at +0x24
NODE_SIZE = 0x14
NODE_TABLE_HEADER = 0x38
SKIP_MARKERS = {"cinematic_skip_start", "cinematic_skip_start_internal"}


class Map:
    def __init__(self, path: Path):
        self.d = path.read_bytes()
        assert self.d[:4] == b"daeh", path
        self.tag_data = struct.unpack_from("<I", self.d, 0x10)[0]
        tag_array, scenario_id = struct.unpack_from("<II", self.d, self.tag_data)
        self.base = tag_array - 0x28
        self.tags = {}
        count = struct.unpack_from("<I", self.d, self.tag_data + 0xC)[0]
        for i in range(count):
            _, _, _, tid, _, data, _, _ = struct.unpack_from("<4s4s4sIIIII", self.d, self.at(tag_array) + i * 32)
            self.tags[tid] = data
        self.scnr = self.at(self.tags[scenario_id])

    def at(self, address: int) -> int:
        return address - self.base + self.tag_data

    def reflexive(self, offset: int):
        count, pointer, _ = struct.unpack_from("<III", self.d, offset)
        return count, (self.at(pointer) if count else 0)

    def data_ref(self, offset: int):
        size, _, _, pointer, _ = struct.unpack_from("<IIIII", self.d, offset)
        return self.d[self.at(pointer):self.at(pointer) + size]

    def ustr(self, tag_id: int) -> list[str]:
        count, p = self.reflexive(self.at(self.tags[tag_id]))
        return [self.data_ref(p + i * 20).decode("utf-16-le").rstrip("\0") for i in range(count)]

    def titles(self):
        texts = self.ustr(struct.unpack_from("<I", self.d, self.scnr + SCNR_HELP_TEXT + 12)[0])
        count, p = self.reflexive(self.scnr + SCNR_TITLES)
        out = []
        for i in range(count):
            e = p + i * TITLE_SIZE
            name = self.d[e + 4:e + 36].split(b"\0")[0].decode()
            text_index = struct.unpack_from("<h", self.d, e + 0x30)[0]
            text = texts[text_index] if 0 <= text_index < len(texts) else "?"
            out.append((name, " ".join(text.split())))
        return out

    def scripts(self):
        nodes = self.data_ref(self.scnr + SCNR_SYNTAX_DATA)
        strings = self.data_ref(self.scnr + SCNR_STRING_DATA)

        def node(nid: int):
            if nid == 0xFFFFFFFF:
                return None
            o = NODE_TABLE_HEADER + (nid & 0xFFFF) * NODE_SIZE
            _, _, _, flags, nxt, soff, data = struct.unpack_from("<HHHHIII", nodes, o)
            text = strings[soff:strings.find(b"\0", soff)].decode(errors="replace")
            return flags, nxt, text, data

        count, p = self.reflexive(self.scnr + SCNR_SCRIPTS)
        scripts = {}
        for i in range(count):
            e = p + i * SCRIPT_SIZE
            name = self.d[e:e + 32].split(b"\0")[0].decode()
            scripts[name] = struct.unpack_from("<I", self.d, e + 0x24)[0]
        return scripts, node


def tree(node, nid):
    """(function name, [argument subtrees]) for a call, or the primitive's text"""
    n = node(nid)
    flags, _, text, data = n
    if flags & 1:
        return text
    children = []
    c = data
    while c != 0xFFFFFFFF:
        children.append(c)
        c = node(c)[1]
    if not children:
        return ("?", [])
    return (str(tree(node, children[0])), [tree(node, c) for c in children[1:]])


def analyse(m: Map):
    titles = m.titles()
    names = {name: i for i, (name, _) in enumerate(titles)}
    scripts, node = m.scripts()
    trees = {s: tree(node, root) for s, root in scripts.items()}

    # (title index, script, skippable) for every call, following script calls
    shown = []
    def walk(t, script, skippable, seen):
        if not isinstance(t, tuple):
            return
        fn, args = t
        if fn == "cinematic_set_title" and args and isinstance(args[0], str) and args[0] in names:
            shown.append((names[args[0]], script, skippable))
        if fn in scripts and fn not in seen:
            walk(trees[fn], fn, skippable, seen | {fn})
        if fn == "if" and args and isinstance(args[0], tuple) and args[0][0] in SKIP_MARKERS:
            walk(args[0], script, skippable, seen)
            if len(args) > 1:
                walk(args[1], script, True, seen)
            for a in args[2:]:
                walk(a, script, skippable, seen)
            return
        for a in args:
            walk(a, script, skippable, seen)

    for s in scripts:
        walk(trees[s], s, False, {s})
    return titles, shown


def current_table() -> dict[str, dict[int, str]]:
    text = (REPO / "HaloAP_launcher/Data/chapter_map.h").read_text(encoding="utf-8-sig")
    out: dict[str, dict[int, str]] = {}
    for m, i, name in re.findall(r'"(\w+):(\d+)",\s*\{\s*\d+,\s*"([^"]*)"', text):
        out.setdefault(m, {})[int(i)] = name
    return out


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv
    maps = Path(args[0]) if args else DEFAULT_MAPS
    table = current_table()
    mismatches = 0
    for code in MAPS:
        titles, shown = analyse(Map(maps / f"{code}.map"))
        print(f"== {code}")
        for i, (name, text) in enumerate(titles):
            calls = [(s, sk) for t, s, sk in shown if t == i]
            where = ", ".join(sorted({s + (" (skippable cutscene)" if sk else "") for s, sk in calls})) or "never shown"
            mapped = table.get(code, {}).get(i)
            flag = ""
            if mapped and norm(mapped) not in norm(text) and norm(text) not in norm(mapped):
                flag = f"   <-- chapter_map.h says {mapped!r}"
                mismatches += 1
            print(f"  {i}: {name:18} {text!r:52} {where}{flag}")
        for i, mapped in table.get(code, {}).items():
            if i >= len(titles):
                print(f"  chapter_map.h maps index {i} ({mapped!r}), which doesn't exist")
                mismatches += 1
    if check:
        print(f"\n{mismatches} mismatches with chapter_map.h")
        return 1 if mismatches else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
