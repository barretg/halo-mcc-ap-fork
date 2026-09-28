from Options import OptionError

from .data.levels import LEVEL_DATA
from .items import skull_items_for_game

# option attribute prefix for each game key (Halo 2's options are h2_*, its key is h2a)
GAME_OPTION_PREFIX = {"ce": "ce", "h2a": "h2", "h3": "h3", "h4": "h4", "reach": "reach"}


def _option(world, game: str, name: str):
    return getattr(world.options, f"{GAME_OPTION_PREFIX[game]}_{name}")


def generate_early(world):
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

        others = [level for level in levels if level != final]
        world.final_missions[game] = final
        world.game_missions[game] = others
        world.starting_missions[game] = world.random.choice([level for level in others if level in playable])
        world.missions_required[game] = min(_option(world, game, "missions_required").value, len(others))
        print(f"{game} final mission: {final}")

    # CE's final mission is still sent on its own for older clients
    world.final_mission = world.final_missions.get("ce", "")

    # Scoring skull items per game, used by the skullsanity "all" completion rule
    world.game_skulls = {game: skull_items_for_game(world, game, scoring=True)
                         for game in world.enabled_games}
