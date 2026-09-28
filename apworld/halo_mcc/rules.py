from .data.levels import LEVEL_DATA
from rule_builder.rules import *
from .mcc_options import SkullSanity

def set_rules(world):
    for game in world.enabled_games:
        final = world.final_missions[game]
        others = world.game_missions[game]

        for level in others:
            entrance = world.multiworld.get_entrance(f"Menu -> {level}", world.player)
            world.set_rule(entrance, Has(f"{level} Access"))

        # The final mission opens once enough of the game's other missions are completed
        # (the client counts completions, not access items)
        entrance = world.multiworld.get_entrance(f"Menu -> {final}", world.player)
        world.set_rule(entrance, AtLeast(world.missions_required[game],
                                         *[CanReachLocation(f"{m} Complete") for m in others]))

        if world.options.skullsanity.value == SkullSanity.option_all:
            skulls = world.game_skulls[game]
            rule = HasFromListUnique(*skulls, count = min(world.options.skulls_required.value, len(skulls)))
            for level in others:
                world.set_rule(world.get_location(f"{level} Complete"), rule)
