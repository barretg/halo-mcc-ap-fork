from BaseClasses import MultiWorld, Region, Entrance
from .data.levels import LEVEL_DATA

def create_regions(world):
    #create menu
    menu_region = Region("Menu", world.player, world.multiworld)
    world.multiworld.regions.append(menu_region)

    #create region for each level of the enabled games
    for level, data in LEVEL_DATA.items():
        if data.game not in world.enabled_games:
            continue

        #create the region
        region = Region(level, world.player, world.multiworld)
        world.multiworld.regions.append(region)

        #create entrance from menu to new region
        entrance_name = f"Menu -> {level}"
        entrance = Entrance(world.player,entrance_name, menu_region)
        menu_region.exits.append(entrance)
        entrance.connect(region)
