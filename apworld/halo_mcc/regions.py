from BaseClasses import MultiWorld, Region, Entrance

def create_regions(world):
    #create menu
    menu_region = Region("Menu", world.player, world.multiworld)
    world.multiworld.regions.append(menu_region)

    #create region for each level of the enabled games
    for level in world.levels:

        #create the region
        region = Region(level, world.player, world.multiworld)
        world.multiworld.regions.append(region)

        #create entrance from menu to new region
        entrance_name = f"Menu -> {level}"
        entrance = Entrance(world.player,entrance_name, menu_region)
        menu_region.exits.append(entrance)
        entrance.connect(region)
