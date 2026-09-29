from Options import OptionError

from .data.levels import LEVEL_DATA, current_level_name
from .items import LEGACY_121_SCORING_SKULL_ITEMS, skull_items_for_game

# option attribute prefix for each game key (Halo 2's options are h2_*, its key is h2a)
GAME_OPTION_PREFIX = {"ce": "ce", "h2a": "h2", "h3": "h3", "h4": "h4", "reach": "reach"}


def _option(world, game: str, name: str):
    return getattr(world.options, f"{GAME_OPTION_PREFIX[game]}_{name}")


def _apply_tracker_slot_data(world) -> dict | None:
    """Universal Tracker regenerates without the player's YAML; copy the real seed's
    options from its slot data so the tracker's logic matches the server's. Returns the
    seed's missions in one form for slot data from any version:
      1.4+: everything is in slot data.
      1.3:  per-game finals and required counts, but no starting missions, game list or
            skull options.
      1.2:  CE only; just CE's final mission and skullsanity.
    A missing starting mission is left as None: the server sends the seed's starting
    Access item like any other, so none is precollected."""
    slot_data = getattr(world.multiworld, "re_gen_passthrough", {}).get(world.game)
    if not slot_data:
        return None
    world.legacy_121 = "final_missions" not in slot_data
    finals = {"ce": slot_data["final_mission"]} if world.legacy_121 else slot_data["final_missions"]
    enabled = slot_data.get("enabled_games", list(finals))
    for game in GAME_OPTION_PREFIX:
        _option(world, game, "enabled").value = int(game in enabled)
    options = world.options
    options.skullsanity.value = slot_data["skullsanity"]
    options.skull_item_mode.value = slot_data.get("skull_item_mode", options.skull_item_mode.default)
    # skulls_required isn't in 1.2/1.3 slot data; assume those seeds kept the default
    options.skulls_required.value = slot_data.get("skulls_required", options.skulls_required.default)
    options.h2_skull_pickups.value = slot_data.get("h2_skull_pickups", 0)
    options.h3_skull_pickups.value = slot_data.get("h3_skull_pickups", 0)
    return {
        "final_missions": {game: current_level_name(level) for game, level in finals.items()},
        "starting_missions": {game: current_level_name(level)
                              for game, level in slot_data.get("starting_missions", {}).items()},
        "missions_required": slot_data.get("missions_required", {}),
    }


def generate_early(world):
    world.legacy_121 = False
    tracker = _apply_tracker_slot_data(world)

    # Games whose missions are in this world
    world.enabled_games = [game for game in GAME_OPTION_PREFIX if _option(world, game, "enabled").value]
    if not world.enabled_games:
        raise OptionError(f"{world.player_name}: at least one game must be enabled")

    world.final_missions = {}
    world.starting_missions = {}
    world.game_missions = {}
    world.missions_required = {}
    for game in world.enabled_games:
        levels = [level for level, data in LEVEL_DATA.items() if data.game == game]
        playable = [level for level in levels if not LEVEL_DATA[level].cinematic]

        # Final mission options count missions from 1 in play order. CE uses 11 for random;
        # the other games use 0.
        choice = _option(world, game, "final_mission").value
        if (game == "ce" and choice == 11) or (game != "ce" and choice == 0):
            final = world.random.choice(playable)
        else:
            final = levels[choice - 1]

        if tracker:
            final = tracker["final_missions"][game]

        others = [level for level in levels if level != final]
        world.final_missions[game] = final
        world.game_missions[game] = others
        world.starting_missions[game] = world.random.choice([level for level in others if level in playable])
        world.missions_required[game] = min(_option(world, game, "missions_required").value, len(others))
        if tracker:
            world.starting_missions[game] = tracker["starting_missions"].get(game)
            world.missions_required[game] = tracker["missions_required"].get(game, len(others))
        print(f"{game} final mission: {final}")

    # CE's final mission is still sent on its own for older clients
    world.final_mission = world.final_missions.get("ce", "")

    # Scoring skull items per game, used by the skullsanity "all" completion rule
    world.game_skulls = {game: skull_items_for_game(world, game, scoring=True)
                         for game in world.enabled_games}
    if world.legacy_121:
        world.game_skulls["ce"] = LEGACY_121_SCORING_SKULL_ITEMS
