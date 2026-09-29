from dataclasses import dataclass, field
from typing import List, Dict
from . import constants
from .missions import MISSIONS, SKULL_PICKUPS, level_name, mission_offset


@dataclass
class LevelData:
    game: str  # game key from skulls.GAME_INFO
    offset: int
    cinematic: bool = False  # no gameplay; never a starting or final mission


# the base level offset is used for the level completion location and the location access item

LEVEL_DATA: Dict[str, LevelData] = {
    "The Pillar of Autumn": LevelData(
        game="ce", offset=constants.PILLER_OF_AUTUMN_OFFSET
    ),
    "Halo (CE)": LevelData(game="ce", offset=constants.HALO_CE_MISSION_OFFSET),
    "The Truth and Reconciliation": LevelData(
        game="ce", offset=constants.TRUTH_AND_RECONCILIATION_OFFSET
    ),
    "The Silent Cartographer": LevelData(
        game="ce", offset=constants.SILENT_CARTOGRAPHER_OFFSET
    ),
    "Assault on the Control Room": LevelData(
        game="ce", offset=constants.ASSAULT_CONTROL_ROOM_OFFSET
    ),
    "343 Guilty Spark": LevelData(
        game="ce", offset=constants.GUILTY_SPARK_OFFSET
    ),
    "The Library": LevelData(
        game="ce", offset=constants.LIBRARY_OFFSET
    ),
    "Two Betrayals": LevelData(
        game="ce", offset=constants.TWO_BETRAYALS_OFFSET
    ),
    "Keyes": LevelData(
        game="ce", offset=constants.KEYS_OFFSET
    ),
    "The Maw": LevelData(
        game="ce", offset=constants.MAW_OFFSET
    ),
}

for _game, _missions in MISSIONS.items():
    for _number, _mission in enumerate(_missions, start=1):
        LEVEL_DATA[level_name(_game, _mission)] = LevelData(
            game=_game, offset=mission_offset(_game, _number), cinematic=_mission.cinematic
        )

# Chapter locations for the games in missions.py: name -> (level, id). CE chapters live in
# halo_ce_location_data.py.
CHAPTER_DATA: Dict[str, tuple[str, int]] = {
    f"{level_name(_game, _mission)} - {_chapter.name}": (
        level_name(_game, _mission),
        mission_offset(_game, _number) + constants.CHAPTER_OFFSET + _n,
    )
    for _game, _missions in MISSIONS.items()
    for _number, _mission in enumerate(_missions, start=1)
    for _n, _chapter in enumerate(_mission.chapters, start=1)
}

# Halo 4 mission starts: several H4 missions show no chapter card when they begin (Dawn
# has none at all), so each playable H4 mission gets a check for loading into it. It
# uses chapter slot 0 (the mission's offset + CHAPTER_OFFSET).
MISSION_START_GAMES = ("h4",)
for _game in MISSION_START_GAMES:
    for _number, _mission in enumerate(MISSIONS[_game], start=1):
        if not _mission.cinematic:
            CHAPTER_DATA[f"{level_name(_game, _mission)} - Mission Start"] = (
                level_name(_game, _mission),
                mission_offset(_game, _number) + constants.CHAPTER_OFFSET,
            )

# Skull pickups in H2 and H3 missions: name -> (level, id, game). IDs are the mission's
# offset + SKULL_LOCATION_OFFSET + n, like CE's. CE's skulls live in halo_ce_location_data.py.
SKULL_LOCATION_DATA: Dict[str, tuple[str, int, str]] = {}
for _game, _by_map in SKULL_PICKUPS.items():
    for _number, _mission in enumerate(MISSIONS[_game], start=1):
        for _n, _skull in enumerate(_by_map.get(_mission.map, ()), start=1):
            SKULL_LOCATION_DATA[f"{level_name(_game, _mission)} - {_skull.name} Skull"] = (
                level_name(_game, _mission),
                mission_offset(_game, _number) + constants.SKULL_LOCATION_OFFSET + _n,
                _game,
            )
