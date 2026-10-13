"""What scenarios are built from: every game's missions, chapters and location ids, read
from the apworld (data/missions.py, data/levels.py) and, for CE, from the launcher's
chapter table (CE's chapters aren't in missions.py)."""

from __future__ import annotations

import importlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# The apworld's data package imports without Archipelago (the world package doesn't)
sys.path.insert(0, str(REPO / "apworld/halo_mcc"))
_missions = importlib.import_module("data.missions")
_levels = importlib.import_module("data.levels")

GAME_CODE = {"ce": 1, "h2a": 2, "h3": 3, "h4": 4, "reach": 6}
GAME_NAME = {"ce": "Halo CE", "h2a": "Halo 2", "h3": "Halo 3", "h4": "Halo 4", "reach": "Halo Reach"}

# The level path each engine's level load takes (see DebugLoadLevel in the DLL). Only
# CE's has been seen in use; the others are what each game's own paths look like.
LOAD_PATH = {
    "ce": "levels\\{0}\\{0}",
    "h2a": "scenarios\\solo\\{0}\\{0}",
    "h3": "levels\\solo\\{0}\\{0}",
    "h4": "environments\\solo\\{0}\\{0}",
    "reach": "levels\\solo\\{0}\\{0}",
}

CE_MAPS = ["a10", "a30", "a50", "b30", "b40", "c10", "c20", "c40", "d20", "d40"]


@dataclass
class Chapter:
    name: str
    keys: tuple            # title indices (Reach: runtime string_ids) that count as it
    location: int


@dataclass
class Skull:
    name: str
    location: int


@dataclass
class Mission:
    game: str              # apworld game key
    number: int            # 1-based, play order
    name: str              # without the game prefix
    map: str
    cinematic: bool
    chapters: list[Chapter] = field(default_factory=list)
    skulls: list[Skull] = field(default_factory=list)
    start_location: int = 0  # H4's "Mission Start"

    @property
    def level(self) -> str:
        """The level name, as Access items and locations use it"""
        return f"{GAME_NAME[self.game]}: {self.name}"

    @property
    def access(self) -> str:
        return f"{self.level} Access"

    @property
    def completion(self) -> int:
        return _missions.mission_offset(self.game, self.number) if self.game != "ce" else \
            _levels.LEVEL_DATA[self.level].offset

    @property
    def load_path(self) -> str:
        return LOAD_PATH[self.game].format(self.map)

    def chapter(self, name: str) -> Chapter:
        return next(c for c in self.chapters if c.name == name)


def _ce_table() -> dict[str, list[tuple[int, int, str]]]:
    """map -> [(title index, location, name)] from the launcher's chapter_map.h"""
    text = (REPO / "HaloAP_launcher/Data/chapter_map.h").read_text(encoding="utf-8-sig")
    out: dict[str, list[tuple[int, int, str]]] = {}
    for m, i, loc, name in re.findall(r'"(\w+):(\d+)",\s*\{\s*(\d+),\s*"([^"]*)"', text):
        out.setdefault(m, []).append((int(i), int(loc), name))
    return out


def load() -> dict[str, list[Mission]]:
    """game key -> missions in play order"""
    games: dict[str, list[Mission]] = {}

    ce_levels = [lv for lv, d in _levels.LEVEL_DATA.items() if d.game == "ce"]
    table = _ce_table()
    ce_skulls = importlib.import_module("data.halo_ce_location_data").CE_LOCATION_DATA
    games["ce"] = []
    for n, (level, map_code) in enumerate(zip(ce_levels, CE_MAPS), start=1):
        m = Mission("ce", n, level.removeprefix("Halo CE: "), map_code, False)
        by_location: dict[int, Chapter] = {}
        for index, location, name in sorted(table.get(map_code, [])):
            if location in by_location:
                by_location[location].keys += (index,)
            else:
                by_location[location] = Chapter(name, (index,), location)
        m.chapters = sorted(by_location.values(), key=lambda c: c.location)
        m.skulls = [Skull(name, d.id) for name, d in ce_skulls.items()
                    if d.type == "Skull" and d.level == level]
        games["ce"].append(m)

    # Reach's keys are string_id names in missions.py; /title takes the runtime ids
    reach_sids = json.loads((REPO / "tools/reach_chapter_sids.json").read_text())
    for game, missions in _missions.MISSIONS.items():
        games[game] = []
        for n, src in enumerate(missions, start=1):
            m = Mission(game, n, src.name, src.map, src.cinematic)
            level = _missions.level_name(game, src)
            for chapter in src.chapters:
                keys = chapter.key if isinstance(chapter.key, tuple) else (chapter.key,)
                if game == "reach":
                    keys = tuple(reach_sids[src.map][k] for k in keys)
                m.chapters.append(Chapter(chapter.name, keys,
                                          _levels.CHAPTER_DATA[f"{level} - {chapter.name}"][1]))
            start = _levels.CHAPTER_DATA.get(f"{level} - Mission Start")
            m.start_location = start[1] if start else 0
            m.skulls = [Skull(s.name, _levels.SKULL_LOCATION_DATA[f"{level} - {s.name} Skull"][1])
                        for s in _missions.SKULL_PICKUPS.get(game, {}).get(src.map, ())]
            games[game].append(m)
    return games
