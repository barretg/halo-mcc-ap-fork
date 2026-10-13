"""Halo 2 chapter cards, checked against MCC's shipped maps rather than the editing kit.

    python tools/h2_shipped_chapters.py [<map> ...] [-v]

MCC's H2 maps (halo2/h2_maps_win64_dx11/*.map) are a 0x380-byte header followed by zlib
streams of 256 KiB each. Decompressed, the scenario's compiled scripts can be read: the
script table (40-byte entries: char name[32]; u16 type; u16 return type; u32 root
expression) and the expression nodes (20 bytes: u16 salt; u16 function/op; u16 value type;
u16 flags; u32 next; i32 string offset; u32 value). Calls to cinematic_set_title take a
cutscene_title atom (value type 16) whose value is the title index the chapter hook reports.

For every chapter in apworld/halo_mcc/data/missions.py this finds the scripts that show its
title and whether a startup or continuous script starts them, through (wake ...) and static
script calls. Found on 2026-10-13: Gravemind's last three cards are never started, as in
the kit; every other H2 chapter is.
"""
import ast, re, struct, sys, zlib
from pathlib import Path
MAPS = Path("/games/SteamLibrary/steamapps/common/Halo The Master Chief Collection/halo2/h2_maps_win64_dx11")
REPO = Path(__file__).resolve().parent.parent
VERBOSE = "-v" in sys.argv


def decompress(path):
    """MCC H2 maps: a 0x380-byte header, then back-to-back zlib streams of 256 KiB each.
    Between some streams there is padding or a stored block; skip ahead to the next stream
    that decompresses."""
    d = path.read_bytes(); out = bytearray(d[:0x380]); off = 0x380
    while off < len(d) - 2:
        z = zlib.decompressobj()
        try:
            data = z.decompress(d[off:off + 0x100000])
            ok = z.eof
        except zlib.error:
            ok = False
        if ok:
            out += data
            off += 0x100000 - len(z.unused_data) if len(d) - off > 0x100000 else len(d) - off - len(z.unused_data)
            continue
        # find the next zlib header (CMF 0x?8 with a valid FCHECK) that really decompresses
        nxt = off + 1
        while nxt < len(d) - 2:
            b0, b1 = d[nxt], d[nxt + 1]
            if b0 & 0x0F == 8 and (b0 * 256 + b1) % 31 == 0:
                try:
                    t = zlib.decompressobj(); t.decompress(d[nxt:nxt + 0x100000])
                    if t.eof:
                        break
                except zlib.error:
                    pass
            nxt += 1
        off = nxt
    return bytes(out)


def entry(d, q):
    """script element: char name[32]; u16 type; u16 return_type; u32 root expression"""
    nm = d[q:q + 32].split(b"\0")[0]
    t, r, root = struct.unpack_from("<HHI", d, q + 32)
    ok = nm and all(32 < c < 127 for c in nm) and t <= 7 and r <= 0xA0 and (root == 0xFFFFFFFF or root >> 31)
    return (nm.decode(), t, root) if ok else None


def script_table(d):
    best = (0, 0)
    seen = set()
    for m in re.finditer(rb"[a-z_][a-z0-9_]{2,31}\x00", d):
        p = m.start()
        if p in seen:
            continue
        if entry(d, p) is None or entry(d, p + 40) is None or entry(d, p + 80) is None:
            continue
        while entry(d, p - 40): p -= 40
        n = 0
        while entry(d, p + n * 40): seen.add(p + n * 40); n += 1
        # the scripts table holds script types beyond 0 and has a mix of dormant/static
        types = {entry(d, p + i * 40)[1] for i in range(n)}
        if n > best[1] and 1 in types and 3 in types:
            best = (p, n)
    p, n = best
    return [entry(d, p + i * 40) for i in range(n)]


def analyse(d):
    scripts = script_table(d)
    roots = [(root & 0xFFFF, root >> 16) for _, _, root in scripts if root != 0xFFFFFFFF]
    base = None
    i0, s0 = roots[0]
    for m in re.finditer(re.escape(struct.pack("<H", s0)), d):
        b = m.start() - i0 * 20
        if b >= 0 and all(b + i * 20 + 2 <= len(d) and struct.unpack_from("<H", d, b + i * 20)[0] == s
                          for i, s in roots[:40]):
            base = b; break
    N = max(i for i, _ in roots) + 3000
    nodes = [struct.unpack_from("<HHHHIiI", d, base + i * 20) for i in range(N) if base + i * 20 + 20 <= len(d)]
    N = len(nodes)
    # owner of every node: walk each script's tree from its root (call nodes: value = first
    # child; every node: next = following sibling)
    own = {}
    for nm, _, root in scripts:
        if root == 0xFFFFFFFF:
            continue
        stack = [root & 0xFFFF]
        while stack:
            i = stack.pop()
            if i >= N or i in own:
                continue
            own[i] = nm
            salt, op, vt, fl, nxt, so, val = nodes[i]
            if nxt != 0xFFFFFFFF:
                stack.append(nxt & 0xFFFF)
            if not fl & 1 and val != 0xFFFFFFFF:
                stack.append(val & 0xFFFF)
    name_of = {i: nm for i, (nm, _, _) in enumerate(scripts)}
    owner = own.get

    refs = {}    # script -> scripts it starts or calls
    titles = {}  # value -> owners, per value type
    for i, (salt, op, vt, fl, nxt, so, val) in enumerate(nodes):
        if not salt & 0x8000:
            continue
        o = None
        # (wake x) style: an atom of type script
        if vt == 10 and val >> 16 in (0, 0xFFFF) and (val & 0xFFFF) in name_of:
            o = owner(i); refs.setdefault(o, set()).add(name_of[val & 0xFFFF])
        # (static_script) style: call node whose flags mark a script call; op is the script index
        if fl & 2 and op in name_of:
            o = o or owner(i); refs.setdefault(o, set()).add(name_of[op])
        if fl & 1 and val >> 16 in (0, 0xFFFF):
            titles.setdefault((vt, val & 0xFFFF), set()).add(i)
    types = {nm: t for nm, t, _ in scripts}
    live = {nm for nm, t, _ in scripts if t in (0, 2)}
    todo = list(live)
    while todo:
        s = todo.pop()
        for c in refs.get(s, ()):
            if c not in live: live.add(c); todo.append(c)
    return scripts, nodes, titles, live, owner, refs


def main():
    src = ast.parse((REPO / "apworld/halo_mcc/data/missions.py").read_text())
    for node in src.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "H2_MISSIONS":
            missions = node.value.elts
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "H2_MISSIONS":
            missions = node.value.elts
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    for call in missions:
        name, map_ = ast.literal_eval(call.args[0]), ast.literal_eval(call.args[1])
        if only and map_ not in only: continue
        chs = [(ast.literal_eval(c.args[0]), ast.literal_eval(c.args[1])) for c in call.args[2].elts
               if not any(k.arg == "unused" for k in c.keywords)] if len(call.args) > 2 else []
        if not chs: continue
        scripts, nodes, titles, live, owner, refs = analyse(decompress(MAPS / f"{map_}.map"))
        print(f"== {name} ({map_}): {len(scripts)} scripts, {len(live)} reachable")
        # the cutscene_title atoms: nodes whose value type is cutscene_title (found as the type
        # of the argument of cinematic_set_title calls: the op every title call shares)
        for cname, key in chs:
            keys = key if isinstance(key, tuple) else (key,)
            owners = set()
            for k in keys:
                for i in titles.get((TITLE_VT, k), ()):
                    owners.add(owner(i))
            shown = owners & live
            if shown:
                state = "ok"
            elif owners:
                state = "never (only in " + ", ".join(sorted(o or "?" for o in owners)) + ", which nothing starts)"
            else:
                state = "never (no script shows it)"
            print(f"  {state:10} {cname} {keys}" + (f"  via {sorted(shown)}" if VERBOSE and shown else ""))


TITLE_VT = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--vt=")), "16"))
if __name__ == "__main__":
    main()
