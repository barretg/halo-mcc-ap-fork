from BaseClasses import ItemClassification, Location

from .items import MCCItem

from .data.halo_ce_location_data import CE_LOCATION_DATA
from .data.levels import CHAPTER_DATA, LEVEL_DATA, SKULL_LOCATION_DATA

#create our own location object that gets everything from the base location object and change game
class MCCLocation(Location):
    game = "Halo Master Chief Collection"

#map all locations to their id
def get_location_name_to_id():
    location_map = {
        **{f"{level} Complete": data.offset for level, data in LEVEL_DATA.items()},
        **{f"{data.level} - {name}": data.id for name, data in CE_LOCATION_DATA.items() if data.type == "Chapter"},
        **{f"{data.level} - {name}": data.id for name, data in CE_LOCATION_DATA.items() if data.type == "Skull"},
        **{name: location_id for name, (_, location_id) in CHAPTER_DATA.items()},
        **{name: location_id for name, (_, location_id, _) in SKULL_LOCATION_DATA.items()},
    }
    return location_map

def completion_event_location(level):
    return f"{level} Completed"

def completion_event_item(game):
    return f"{game} Mission Completed"

#create locations and place them in their region
def create_locations(world):
    final_missions = set(world.final_missions.values())
    for level, data in LEVEL_DATA.items():
        if data.game in world.enabled_games and level not in final_missions:
            region = world.get_region(level)
            location = MCCLocation(world.player, f"{level} Complete", data.offset, region)
            region.locations.append(location)
            # Event twin of the completion, counted to open the game's final mission
            event = MCCLocation(world.player, completion_event_location(level), None, region)
            event.place_locked_item(MCCItem(completion_event_item(data.game), ItemClassification.progression,
                                            None, world.player))
            region.locations.append(event)

    if "ce" in world.enabled_games:
        for location, data in CE_LOCATION_DATA.items():
            if data.type in ("Chapter", "Skull"):
                region = world.get_region(data.level)
                location = MCCLocation(world.player, f"{data.level} - {location}", data.id, region)
                region.locations.append(location)

    for name, (level, location_id) in CHAPTER_DATA.items():
        if LEVEL_DATA[level].game in world.enabled_games:
            region = world.get_region(level)
            region.locations.append(MCCLocation(world.player, name, location_id, region))

    skull_options = {"h2a": world.options.h2_skull_pickups, "h3": world.options.h3_skull_pickups}
    for name, (level, location_id, game) in SKULL_LOCATION_DATA.items():
        if game in world.enabled_games and skull_options[game].value:
            region = world.get_region(level)
            region.locations.append(MCCLocation(world.player, name, location_id, region))
