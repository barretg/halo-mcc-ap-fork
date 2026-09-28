from BaseClasses import Item, ItemClassification
from .data.constants import *
from .data.levels import LEVEL_DATA, LevelData
from .data.skulls import (GAME_INFO, GAME_SKULLS, NON_SCORING_SKULLS, SHARED_SKULL_GAME_CODE,
                          SKULLS, SKULLS_BY_NAME)
from .mcc_options import SkullItemMode, SkullSanity


def skull_item_name(skull: str, game: str | None) -> str:
    """Per-game item name when game is given, shared item name when it's None."""
    if game is None:
        return f"{skull} Skull"
    return f"{GAME_INFO[game][1]}: {skull} Skull"


def _skull_item_id(skull: str, game: str | None) -> int:
    code = SHARED_SKULL_GAME_CODE if game is None else GAME_INFO[game][0]
    return SKULL_OFFSET + code * 100 + SKULLS_BY_NAME[skull].bit + 1


# item name -> (id, skull name) for every skull item, per-game and shared
SKULL_ITEMS: dict[str, tuple[int, str]] = {
    **{skull_item_name(s.name, None): (_skull_item_id(s.name, None), s.name) for s in SKULLS},
    **{skull_item_name(s.name, game): (_skull_item_id(s.name, game), s.name)
       for s in SKULLS for game in s.games},
}


def skull_items_for_game(world, game: str, scoring: bool) -> list[str]:
    """Item names for a game's scoring or non-scoring skulls under the world's skull item mode."""
    skulls = GAME_SKULLS[game] if scoring else NON_SCORING_SKULLS[game]
    shared = world.options.skull_item_mode == SkullItemMode.option_shared
    return [skull_item_name(skull, None if shared else game) for skull in skulls]


# create our own item object that has the game set correctly, everything else is the same as the base item object
class MCCItem(Item):
    game = "Halo Master Chief Collection"


# this is what maps items to their ID
def get_item_name_to_id():
    item_table = {
        "filler": 1,
        **{f"{level} Access": data.offset for level, data in LEVEL_DATA.items()},
        **{name: item_id for name, (item_id, _) in SKULL_ITEMS.items()}
    }
    return item_table


# gives us the name of a filler item
def get_filler_item_name(world):
    return "filler"


# fill unfilled locations with filler from this world
def create_filler(world, filled_locations):
    fillerpool: list[Item] = []
    unfilled_locations = world.multiworld.get_unfilled_locations(world.player)
    needed_items = len(unfilled_locations) - filled_locations
    for i in range(needed_items):
        fillerpool.append(create_item_with_data(world, "filler"))

    return fillerpool


# create all items for the world
def create_items(world):
    itempool: list[Item] = []
    for game in world.enabled_games:
        for level in world.game_missions[game]:
            if level == world.starting_missions[game]:
                world.multiworld.push_precollected(create_item_with_data(world, f"{level} Access"))
            else:
                itempool.append(create_item_with_data(world, f"{level} Access"))

    # Scoring skull items when skullsanity is all/inverted, non-scoring ones for any
    # skullsanity. In shared mode a skull several games have is still one item.
    skull_items: list[str] = []
    for game in world.enabled_games:
        if world.options.skullsanity >= 2:
            skull_items += skull_items_for_game(world, game, scoring=True)
        if world.options.skullsanity >= 1:
            skull_items += skull_items_for_game(world, game, scoring=False)
    for name in dict.fromkeys(skull_items):
        itempool.append(create_item_with_data(world, name))

    itempool.extend(create_filler(world, len(itempool)))

    world.multiworld.itempool += itempool


# creates a single item with its classification and ID
def create_item_with_data(world, name):
    if "Access" in name:
        classification = ItemClassification.progression
        real_name = name.replace(" Access", "")
        level_data = LEVEL_DATA[real_name]
        item_id = level_data.offset
    elif name in SKULL_ITEMS:
        item_id, skull = SKULL_ITEMS[name]
        # Scoring skulls gate mission completion under skullsanity "all"; non-scoring ones don't.
        if SKULLS_BY_NAME[skull].scoring:
            classification = ItemClassification.progression
        else:
            classification = ItemClassification.useful
    else:
        classification = ItemClassification.filler
        item_id = 1

    return MCCItem(name, classification, item_id, world.player)
