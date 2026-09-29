from worlds.AutoWorld import World
from .webWorld import MCCWeb
from .mcc_options import MCCOptions
from . import regions, locations, items, rules, generate_early, goal
from typing import Any
from .data.levels import CURRENT_TO_LEGACY_CE_LEVEL, LEGACY_ITEM_NAMES

class MCCWorld(World):
    """
    yipee
    """

    game = "Halo The Master Chief Collection"
    options_dataclass = MCCOptions
    options: MCCOptions
    required_client_version = (1, 2, 0)
    web = MCCWeb()
    # Universal Tracker regenerates from slot data (see interpret_slot_data)
    ut_can_gen_without_yaml = True

    #connects item names to their ID
    item_name_to_id = items.get_item_name_to_id()
    ##same thing as items but for locations
    location_name_to_id = locations.get_location_name_to_id()
    # Pre-1.4 CE names as groups of one, so old YAML options and !hint names still work
    item_name_groups = {old: {new} for old, new in LEGACY_ITEM_NAMES.items()}
    location_name_groups = {old: {new} for old, new in locations.get_legacy_location_names().items()}
    final_mission:str  # CE's final mission, "" when CE is off
    final_missions: dict[str, str]  # game key -> final mission level
    starting_missions: dict[str, str]  # game key -> precollected mission level
    game_missions: dict[str, list[str]]  # game key -> its levels other than the final one
    missions_required: dict[str, int]  # game key -> missions needed to open the final one
    enabled_games: list[str]
    game_skulls: dict[str, list[str]]

    #creates all logic for locations, entrances, and goal
    def set_rules(self):
        rules.set_rules(self)
        goal.set_goal(self)

    #create regions and place locations inside the regions
    def create_regions(self):
        regions.create_regions(self)
        locations.create_locations(self)

    #creates all items
    def create_items(self):
        items.create_items(self)

    #creates one item with needed information
    def create_item(self, name: str):
        return items.create_item_with_data(self, name)

    #get the name of a filler item, used to fill unfilled locations
    def get_filler_item_name(self):
        return items.get_filler_item_name(self)

    def generate_early(self):
        generate_early.generate_early(self)

    def fill_slot_data(self) -> dict[str, Any]:
        # CE names stay in their pre-1.4 form in slot data so older launchers still read
        # them; newer launchers and generate_early accept either form.
        legacy = lambda level: CURRENT_TO_LEGACY_CE_LEVEL.get(level, level)
        return {
            "final_mission": legacy(self.final_mission),
            "skullsanity": self.options.skullsanity.value,
            "skull_item_mode": self.options.skull_item_mode.value,
            "final_missions": {game: legacy(level) for game, level in self.final_missions.items()},
            "missions_required": self.missions_required,
            # Read back by Universal Tracker's regeneration, see generate_early
            "starting_missions": {game: legacy(level) for game, level in self.starting_missions.items()},
            "enabled_games": self.enabled_games,
            "skulls_required": self.options.skulls_required.value,
            "h2_skull_pickups": self.options.h2_skull_pickups.value,
            "h3_skull_pickups": self.options.h3_skull_pickups.value,
        }

    # Universal Tracker: hands the slot data back to generate_early as re_gen_passthrough
    @staticmethod
    def interpret_slot_data(slot_data: dict[str, Any]) -> dict[str, Any]:
        return slot_data