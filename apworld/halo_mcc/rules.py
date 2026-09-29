from .data.levels import LEVEL_DATA
from rule_builder.rules import *
from .locations import completion_event_item, completion_event_location
from .mcc_options import SkullSanity

def set_rules(world):
    for game in world.enabled_games:
        final = world.final_missions[game]
        others = world.game_missions[game]

        for level in others:
            entrance = world.multiworld.get_entrance(f"Menu -> {level}", world.player)
            world.set_rule(entrance, Has(f"{level} Access"))

        # The final mission opens once enough of the game's other missions are completed
        # (the client counts completions, not access items). Each completion drops an event
        # item; AtLeast would do this directly but needs a newer Archipelago.
        entrance = world.multiworld.get_entrance(f"Menu -> {final}", world.player)
        if world.legacy_121:
            # 1.2.1 seeds (rebuilt by Universal Tracker) open it with every other Access item
            world.set_rule(entrance, HasAll(*[f"{level} Access" for level in others]))
        else:
            world.set_rule(entrance, Has(completion_event_item(game), count = world.missions_required[game]))

        if world.options.skullsanity.value == SkullSanity.option_all:
            skulls = world.game_skulls[game]
            rule = HasFromListUnique(*skulls, count = min(world.options.skulls_required.value, len(skulls)))
            for level in others:
                world.set_rule(world.get_location(f"{level} Complete"), rule)
                world.set_rule(world.get_location(completion_event_location(level)), rule)
