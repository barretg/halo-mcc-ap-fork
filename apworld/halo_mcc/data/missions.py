"""
Missions and chapters for Halo 2, Halo 3, Halo 4 and Halo Reach.

Chapter lists come from the live hook mapping in Docs/hook-map-h2-h3-h4-reach.md.
Each chapter's `key` is what the DLL will see when the card shows:
  - H2/H3/H4: the index passed to the chapter title function (index into the map's
    title block). A tuple means any of those indices counts as the same chapter.
  - Reach:    the chapter's string_id name in the map (resolved to a runtime string_id
    per map; see the doc).
The apworld only uses names and order; keys are here so the DLL tables and these stay
in one place.

IDs follow constants.py: game * 100000 + mission * 1000 for the mission (access item and
completion location), + CHAPTER_OFFSET + n for its nth chapter.

cinematic missions have no gameplay: they still have a completion location, but they are
never picked as a starting or final mission.
"""

from __future__ import annotations
from typing import NamedTuple

from .skulls import GAME_INFO


class Chapter(NamedTuple):
    name: str
    key: int | tuple[int, ...] | str


class Mission(NamedTuple):
    name: str
    map: str
    chapters: tuple[Chapter, ...] = ()
    cinematic: bool = False


C = Chapter

H2_MISSIONS: list[Mission] = [
    Mission("The Heretic", "00a_introduction", cinematic=True),
    Mission("The Armory", "01a_tutorial", (C("One Size Fits All", 0),)),
    Mission("Cairo Station", "01b_spacestation", (
        C("Home Field Advantage", 0), C("Priority Shift", 1),
        C("Authorized Personnel Only", 2), C("Return to Sender", 3))),
    Mission("Outskirts", "03a_oldmombasa", (
        C("They'll Regret That Too", 0), C("A Day at the Beach", 1), C("Speed Zone Ahead", 2))),
    # First card's text changes with difficulty (Armor-Plating / Grinding Treads / Superior Firepower)
    Mission("Metropolis", "03b_newmombasa", (
        C("Ladies Like Armor-Plating", (0, 1, 2)),
        C("This Town Ain't Big Enough for Both of Us", 3), C("Field Expedient", 4))),
    Mission("The Arbiter", "04a_gasgiant", (
        C("A Whisper in the Storm", 0), C("To the Hunt", 1))),
    Mission("The Oracle", "04b_floodlab", (
        C("Juggernaut", 0), C("Hey, Watch This!", 1), C("Dead or Alive...Actually, Just Dead", 2))),
    Mission("Delta Halo", "05a_deltaapproach", (
        C("Helljumpers", 0), C("You Break It, You Buy It", 1),
        C("Off the Rock, Through the Bush, Nothing But Jackal", 2))),
    # Index 2 ("Pressure") exists in the block but isn't confirmed to show, so it's left out
    Mission("Regret", "05b_deltatowers", (
        C("Testament", 0), C("One-Way Ticket", 1),
        C("Sorry, Were You in the Middle of Something?", 3))),
    Mission("Sacred Icon", "06a_sentinelwalls", (
        C("Uncomfortable Silence", 0), C("Buyer's Remorse", 1), C("100,000 Years' War", 2))),
    Mission("Quarantine Zone", "06b_floodzone", (
        C("Objects in Mirror are Larger Than They Appear", 0), C("Healthy Competition", 1),
        C("Shooting Gallery", 2), C("That Old, Familiar Feeling", 3))),
    Mission("Gravemind", "07a_highcharity", (
        C("Inside Job", 0), C("You Can Thank Me Later", 1),
        C("Grudge-Match", 2), C("Turning in Their Graves", 3))),
    Mission("Uprising", "08a_deltacliffs", (
        C("Oh, So That's How it Is", 0), C("Step Aside, Let the Man Go Through", 1),
        C("Fight Club", 2))),
    Mission("High Charity", "07b_forerunnership", (
        C("Cross-Purposes", 0), C("Please, Make Yourself at Home", 1),
        C("Sanctified", 2), C("Once More, With Feeling", 3))),
    Mission("The Great Journey", "08b_deltacontrol", (
        C("Your Ass, My Size-24 Hoof", 0), C("Backseat Driver", 1),
        C("Delusions and Grandeur", 2))),
]

H3_MISSIONS: list[Mission] = [
    Mission("Arrival", "005_intro", cinematic=True),
    Mission("Sierra 117", "010_jungle", (
        C("Walk It Off", 0), C("Charlie Foxtrot", 1), C("Quid Pro Quo", 2))),
    Mission("Crow's Nest", "020_base", (
        C("Know Your Role...", 0), C("Gift with Purchase", 1),
        C("Last One Out, Get the Lights", 2))),
    Mission("Tsavo Highway", "030_outskirts", (
        C("Full Contact Safari", 0), C("The Broken Path", 1))),
    Mission("The Storm", "040_voi", (
        C("Ghost Town", 0), C("Think Big", 1), C("Judgment", 2))),
    Mission("Floodgate", "050_floodvoi", (
        C("It Followed Me Home", 0), C("Shadow of Intent", 1), C("Infinite Devil Machine", 2))),
    Mission("The Ark", "070_waste", (
        C("Installation 00", 0), C("Forward Unto Dawn", 1), C("Real Men Don't Read Maps", 2))),
    Mission("The Covenant", "100_citadel", (
        C("Trident", 0), C("If You Want it Done Right...", 1),
        C("Journey's End", 2), C("Revelation", 3))),
    Mission("Cortana", "110_hc", (
        C("Rampant", 0), C("Nor Hell a Fury...", 1))),
    Mission("Halo", "120_halo", (
        C("Full Circle", 0), C("The Way the World Ends", 1))),
    Mission("Epilogue", "130_epilogue", cinematic=True),
]

H4_MISSIONS: list[Mission] = [
    Mission("Prologue", "m05_prologue", cinematic=True),
    Mission("Dawn", "m10_crash"),
    Mission("Requiem", "m020", (
        C("Requiem", (15, 19)), C("A Star to Steer By", 16), C("The Gateway", 17))),
    Mission("Forerunner", "m30_cryptum", (
        C("Buried and Forgotten", 35), C("Enemy of My Enemy", 36),
        C("Almost Home", 37), C("Next Stop, Certain Death", 38))),
    Mission("Infinity", "m60_rescue", (
        C("Infinity", 36), C("Reunited", 37), C("The Gun Show", 39),
        C("Shining Armor", 40), C("Eviction Proceedings", 41))),
    Mission("Reclaimer", "m40_invasion", (
        C("Size Matters", 67), C("The Gravity of the Situation", 66))),
    Mission("Shutdown", "m70_liftoff", (
        C("Once More Unto the Breach", 16), C("Change of Plan", 18))),
    Mission("Composer", "m80_delta", (
        C("Any Landing You Can Walk Away From", 1), C("The Composer", 2),
        C("All Things Lost and Found...", 4))),
    Mission("Midnight", "m90_sacrifice", (
        C("One Last Shot", 0), C("From the Cradle...", 2),
        C("...To the Grave", 3), C("Old Friends", 10))),
    Mission("Epilogue", "m95_epilogue", cinematic=True),
]

REACH_MISSIONS: list[Mission] = [
    Mission("Noble Actual", "m05", cinematic=True),
    Mission("Winter Contingency", "m10", (
        C("NOBLE Team", "chapter_01"), C("Rebels Don't Leave Plasma Burns...", "chapter_02"),
        C("Skeleton Crew", "chapter_03"))),
    Mission("ONI: Sword Base", "m20", (
        C("The Best Defense...", "ct_courtyard"), C("Get the Hell Off My Lawn!", "ct_valley"),
        C("Office of Naval Intelligence", "ct_sword"), C("Minimum Safe Distance", "ct_return"))),
    Mission("Nightfall", "m30", (
        C("...Too Quiet", "ct_quiet"), C("Let Sleeping Dogs Lie", "ct_mule"),
        C("I'll Just Leave This Here...", "ct_settlement"))),
    Mission("Tip of the Spear", "m35", (
        C("Tempest Perimeter", "chapter_01"), C("Hand Over Fist", "chapter_02"),
        C("The Spire", "chapter_03"))),
    # The corvette card is picked at random from two titles with the same text
    Mission("Long Night of Solace", "m45", (
        C("First Floor: Aliens, Beaches, Secret Launch Stations", "ct_beach"),
        C("Operation: Upper Cut", "ct_wafer"),
        C("And the Horse You Flew In On...", ("ct_corvette", "ct_corvette_alt")))),
    Mission("Exodus", "m50", (
        C("The Devil His Due", "ct_act1"), C("Too Close to the Sun", "ct_act2"),
        C("I Should Have Become a Watchmaker", "ct_act3"))),
    Mission("New Alexandria", "m52", (
        C("Fly by Night", "ct_start"), C("Last One Out... Turn Out the Lights", "ct_final"))),
    Mission("The Package", "m60", (
        C("Torch and Burn", "ct_start"), C("Latchkey", "ct_courtyard"),
        C("This Cave is Not a Natural Formation", "ct_ice_cave"))),
    Mission("The Pillar of Autumn", "m70", (
        C("Once More unto the Breach", "ct_dirtroad"), C("This Town Isn't Big Enough", "ct_blockade"),
        C("Shipbreaker", "ct_wall"), C("Keyes", "ct_platform"))),
    Mission("Lone Wolf", "m70_bonus", (
        C("There'll be Another Time...", "ct_hill"),)),
]

MISSIONS: dict[str, list[Mission]] = {
    "h2a": H2_MISSIONS,
    "h3": H3_MISSIONS,
    "h4": H4_MISSIONS,
    "reach": REACH_MISSIONS,
}


def level_name(game: str, mission: Mission) -> str:
    """Region/level name. Prefixed with the game so names can't clash with CE's."""
    return f"{GAME_INFO[game][1]}: {mission.name}"


def mission_offset(game: str, number: int) -> int:
    """number is the 1-based mission number in play order."""
    return GAME_INFO[game][0] * 100000 + number * 1000
