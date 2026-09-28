"""
Skull catalog for Halo MCC Archipelago.

Source: https://www.halopedia.org/MCC:Skulls (which skulls each game has in MCC).

bit     - bit in MCC's lobby skull bitmask (one 64-bit mask shared by every game; the
          DLL forces bits on/off there). Bits are the alphabetical order of MCC's skull
          list, so they don't follow the item names here.
scoring - score multiplier above 1.00x. Non-scoring skulls (1.00x and 0.00x) are the
          ones skullsanity "non_scoring" locks off.
games   - games that have the skull in MCC.

Skull item IDs: SKULL_OFFSET + game_code * 100 + bit + 1, where game_code is the game
digit from constants.py (1 = CE ... 6 = Reach) for per-game items, or
SHARED_SKULL_GAME_CODE for shared items. IDs SKULL_OFFSET + 1..23 were the 1.2.1 CE
items; the client still decodes them for old seeds, so don't reuse that range.
"""

from __future__ import annotations
from typing import NamedTuple


class SkullData(NamedTuple):
    name: str
    bit: int
    scoring: bool
    games: tuple[str, ...]


SKULLS: list[SkullData] = [
    SkullData("Anger",                  0,  True,  ("ce", "h2a", "h3", "odst")),
    SkullData("Assassins",              1,  True,  ("h2a",)),
    SkullData("Bandana",                2,  False, ("ce", "h2a", "h3", "odst", "h4", "reach")),
    SkullData("Black Eye",              3,  True,  ("ce", "h2a", "h3", "odst", "h4", "reach")),
    SkullData("Blind",                  4,  True,  ("ce", "h2a", "h3", "odst", "h4", "reach")),
    SkullData("Bonded Pair",            5,  False, ("h2a", "h3", "odst")),
    SkullData("Boom",                   6,  False, ("ce", "h2a", "h3", "odst")),
    SkullData("Catch",                  7,  True,  ("ce", "h2a", "h3", "odst", "h4", "reach")),
    SkullData("Cowbell",                8,  False, ("h3", "odst", "h4", "reach")),
    SkullData("Envy",                   9,  False, ("h2a",)),
    SkullData("Eye Patch",              10, True,  ("ce", "h2a", "h3", "odst")),
    SkullData("Famine",                 11, True,  ("ce", "h2a", "h3", "odst", "h4", "reach")),
    SkullData("Feather",                12, False, ("h2a",)),
    SkullData("Fog",                    13, True,  ("ce", "h2a", "h3", "h4", "reach")),
    SkullData("Foreign",                14, True,  ("ce", "h3", "odst")),
    SkullData("Ghost",                  15, False, ("ce", "h2a", "h3", "odst")),
    SkullData("Grunt Birthday Party",   16, False, ("ce", "h2a", "h3", "odst", "h4", "reach")),
    SkullData("Grunt Funeral",          17, False, ("ce", "h2a")),
    SkullData("Iron",                   18, True,  ("ce", "h2a", "h3", "odst", "h4", "reach")),
    SkullData("IWHBYD",                 19, False, ("h2a", "h3", "odst", "h4", "reach")),
    SkullData("Jacked",                 20, True,  ("h2a", "h3", "odst")),
    SkullData("Malfunction",            21, False, ("ce", "h2a", "h3", "odst")),
    SkullData("Masterblaster",          22, True,  ("h2a", "h3", "odst")),
    SkullData("Mythic",                 23, True,  ("ce", "h2a", "h3", "odst", "h4", "reach")),
    SkullData("Pinata",                 24, False, ("ce", "h2a", "h3", "odst")),
    SkullData("Prophet Birthday Party", 25, False, ("h2a",)),
    SkullData("Recession",              26, True,  ("ce", "h2a", "h3", "odst")),
    SkullData("Scarab",                 27, False, ("h2a",)),
    SkullData("SO...ANGRY...",          28, False, ("h2a", "h3", "odst")),
    SkullData("Sputnik",                29, False, ("ce", "h2a")),
    SkullData("Streaking",              30, True,  ("h2a",)),
    SkullData("Swarm",                  31, False, ("h2a", "h3", "odst")),
    SkullData("That's Just... Wrong",   32, True,  ("ce", "h2a", "h3", "odst")),
    SkullData("They Come Back",         33, False, ("h2a", "h3")),
    SkullData("Thunderstorm",           34, True,  ("ce", "h2a", "h3", "odst", "h4", "reach")),
    SkullData("Tilt",                   35, True,  ("h3", "odst", "h4", "reach")),
    SkullData("Tough Luck",             36, True,  ("ce", "h3", "odst", "h4", "reach")),
    SkullData("Acrophobia",             37, False, ("ce", "h2a", "h3", "odst", "h4", "reach")),
]

SKULLS_BY_NAME: dict[str, SkullData] = {s.name: s for s in SKULLS}

# Game key -> (ID game digit, item name prefix used for per-game skull items)
GAME_INFO: dict[str, tuple[int, str]] = {
    "ce":    (1, "Halo CE"),
    "h2a":   (2, "Halo 2"),
    "h3":    (3, "Halo 3"),
    "h4":    (4, "Halo 4"),
    "odst":  (5, "Halo 3 ODST"),
    "reach": (6, "Halo Reach"),
}
SHARED_SKULL_GAME_CODE = 7

# Scoring skulls per game, alphabetical
GAME_SKULLS: dict[str, list[str]] = {
    game: sorted(s.name for s in SKULLS if s.scoring and game in s.games) for game in GAME_INFO
}

# Non-scoring skulls per game, alphabetical
NON_SCORING_SKULLS: dict[str, list[str]] = {
    game: sorted(s.name for s in SKULLS if not s.scoring and game in s.games) for game in GAME_INFO
}

NON_SCORING: frozenset[str] = frozenset(s.name for s in SKULLS if not s.scoring)
