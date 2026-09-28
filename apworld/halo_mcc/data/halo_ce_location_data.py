from dataclasses import dataclass, field
from typing import List, Dict
from . import constants


@dataclass
class HaloCeData:
    type: str
    level: str
    id: int


CE_LOCATION_DATA: Dict[str, HaloCeData] = {
    "Reveille": HaloCeData(
        type="Chapter",
        level="The Pillar of Autumn",
        id=constants.PILLER_OF_AUTUMN_OFFSET + constants.CHAPTER_OFFSET + 1,
    ),  # 101011
    "AI Constructs and Cyborgs First!": HaloCeData(
        type="Chapter",
        level="The Pillar of Autumn",
        id=constants.PILLER_OF_AUTUMN_OFFSET + constants.CHAPTER_OFFSET + 2,
    ),  # 101012
    "Iron Skull": HaloCeData(
        type="Skull",
        level="The Pillar of Autumn",
        id=constants.PILLER_OF_AUTUMN_OFFSET + constants.SKULL_LOCATION_OFFSET + 1,
    ),  # 101021
    "Flawless Cowboy": HaloCeData(
        type="Chapter",
        level="Halo (CE)",
        id=constants.HALO_CE_MISSION_OFFSET + constants.CHAPTER_OFFSET + 1,
    ),  # 102011
    "Reunion Tour": HaloCeData(
        type="Chapter",
        level="Halo (CE)",
        id=constants.HALO_CE_MISSION_OFFSET + constants.CHAPTER_OFFSET + 2,
    ),  # 102012
    "Mythic Skull": HaloCeData(
        type="Skull",
        level="Halo (CE)",
        id=constants.HALO_CE_MISSION_OFFSET + constants.SKULL_LOCATION_OFFSET + 1,
    ),  # 102021
    "Boom Skull": HaloCeData(
        type="Skull",
        level="Halo (CE)",
        id=constants.HALO_CE_MISSION_OFFSET + constants.SKULL_LOCATION_OFFSET + 2,
    ),  # 102022
    "The Truth and Reconciliation": HaloCeData(
        type="Chapter",
        level="The Truth and Reconciliation",
        id=constants.TRUTH_AND_RECONCILIATION_OFFSET + constants.CHAPTER_OFFSET + 1,
    ),  # 103011
    "Into the Belly of the Beast": HaloCeData(
        type="Chapter",
        level="The Truth and Reconciliation",
        id=constants.TRUTH_AND_RECONCILIATION_OFFSET + constants.CHAPTER_OFFSET + 2,
    ),  # 103012
    "Shut Up and Get Behind me... Sir": HaloCeData(
        type="Chapter",
        level="The Truth and Reconciliation",
        id=constants.TRUTH_AND_RECONCILIATION_OFFSET + constants.CHAPTER_OFFSET + 3,
    ),  # 103013
    "Foreign Skull": HaloCeData(
        type="Skull",
        level="The Truth and Reconciliation",
        id=constants.TRUTH_AND_RECONCILIATION_OFFSET
        + constants.SKULL_LOCATION_OFFSET
        + 2,
    ),  # 103022
    "The Silent Cartographer": HaloCeData(
        type="Chapter",
        level="The Silent Cartographer",
        id=constants.SILENT_CARTOGRAPHER_OFFSET + constants.CHAPTER_OFFSET + 1,
    ),  # 104011
    "Its Quiet...": HaloCeData(
        type="Chapter",
        level="The Silent Cartographer",
        id=constants.SILENT_CARTOGRAPHER_OFFSET + constants.CHAPTER_OFFSET + 2,
    ),  # 104012
    "Shafted": HaloCeData(
        type="Chapter",
        level="The Silent Cartographer",
        id=constants.SILENT_CARTOGRAPHER_OFFSET + constants.CHAPTER_OFFSET + 3,
    ),  # 104012
    "Famine Skull": HaloCeData(
        type="Skull",
        level="The Silent Cartographer",
        id=constants.SILENT_CARTOGRAPHER_OFFSET + constants.SKULL_LOCATION_OFFSET + 1,
    ),  # 104021
    "Bandana Skull": HaloCeData(
        type="Skull",
        level="The Silent Cartographer",
        id=constants.SILENT_CARTOGRAPHER_OFFSET + constants.SKULL_LOCATION_OFFSET + 2,
    ),  # 104022
    "I Would Have Been Your Daddy...": HaloCeData(
        type="Chapter",
        level="Assault on the Control Room",
        id=constants.ASSAULT_CONTROL_ROOM_OFFSET + constants.CHAPTER_OFFSET + 1,
    ),  # 105011
    "Rolling Thunder": HaloCeData(
        type="Chapter",
        level="Assault on the Control Room",
        id=constants.ASSAULT_CONTROL_ROOM_OFFSET + constants.CHAPTER_OFFSET + 2,
    ),  # 105012
    "If I Had a Super Weapon...": HaloCeData(
        type="Chapter",
        level="Assault on the Control Room",
        id=constants.ASSAULT_CONTROL_ROOM_OFFSET + constants.CHAPTER_OFFSET + 3,
    ),  # 105013
    "Fog Skull": HaloCeData(
        type="Skull",
        level="Assault on the Control Room",
        id=constants.ASSAULT_CONTROL_ROOM_OFFSET + constants.SKULL_LOCATION_OFFSET + 1,
    ),  # 105021
    "Malfunction Skull": HaloCeData(
        type="Skull",
        level="Assault on the Control Room",
        id=constants.ASSAULT_CONTROL_ROOM_OFFSET + constants.SKULL_LOCATION_OFFSET + 2,
    ),  # 105022
    "Well Enough Alone": HaloCeData(
        type="Chapter",
        level="343 Guilty Spark",
        id=constants.GUILTY_SPARK_OFFSET + constants.CHAPTER_OFFSET + 1,
    ),  # 106011
    "The Flood": HaloCeData(
        type="Chapter",
        level="343 Guilty Spark",
        id=constants.GUILTY_SPARK_OFFSET + constants.CHAPTER_OFFSET + 2,
    ),  # 106012
    "343 Guilty Spark": HaloCeData(
        type="Chapter",
        level="343 Guilty Spark",
        id=constants.GUILTY_SPARK_OFFSET + constants.CHAPTER_OFFSET + 3,
    ),  # 106013
    "Recession Skull": HaloCeData(
        type="Skull",
        level="343 Guilty Spark",
        id=constants.GUILTY_SPARK_OFFSET + constants.SKULL_LOCATION_OFFSET + 1,
    ),  # 106021
    "The Library": HaloCeData(
        type="Chapter",
        level="The Library",
        id=constants.LIBRARY_OFFSET + constants.CHAPTER_OFFSET + 1,
    ),  # 107011
    "Wait, it Gets Worse!": HaloCeData(
        type="Chapter",
        level="The Library",
        id=constants.LIBRARY_OFFSET + constants.CHAPTER_OFFSET + 2,
    ),  # 107012
    "But I Don't Want to Ride the Elevator!": HaloCeData(
        type="Chapter",
        level="The Library",
        id=constants.LIBRARY_OFFSET + constants.CHAPTER_OFFSET + 3,
    ),  # 107013
    "Fourth Floor: Tools, Guns, Keys To Super Weapons": HaloCeData(
        type="Chapter",
        level="The Library",
        id=constants.LIBRARY_OFFSET + constants.CHAPTER_OFFSET + 4,
    ),  # 107014
    "Black Eye Skull": HaloCeData(
        type="Skull",
        level="The Library",
        id=constants.LIBRARY_OFFSET + constants.SKULL_LOCATION_OFFSET + 1,
    ),  # 107021
    "Eye Patch Skull": HaloCeData(
        type="Skull",
        level="The Library",
        id=constants.LIBRARY_OFFSET + constants.SKULL_LOCATION_OFFSET + 2,
    ),  # 107022
    "The Gun Pointed at the Head of the Universe": HaloCeData(
        type="Chapter",
        level="Two Betrayals",
        id=constants.TWO_BETRAYALS_OFFSET + constants.CHAPTER_OFFSET + 1,
    ),  # 108011
    "Breaking Stuff to look Tough": HaloCeData(
        type="Chapter",
        level="Two Betrayals",
        id=constants.TWO_BETRAYALS_OFFSET + constants.CHAPTER_OFFSET + 2,
    ),  # 108012
    "The Tunnels Below": HaloCeData(
        type="Chapter",
        level="Two Betrayals",
        id=constants.TWO_BETRAYALS_OFFSET + constants.CHAPTER_OFFSET + 3,
    ),  # 108013
    "Final Run": HaloCeData(
        type="Chapter",
        level="Two Betrayals",
        id=constants.TWO_BETRAYALS_OFFSET + constants.CHAPTER_OFFSET + 4,
    ),  # 108014
    "Pinata Skull": HaloCeData(
        type="Skull",
        level="Two Betrayals",
        id=constants.TWO_BETRAYALS_OFFSET + constants.SKULL_LOCATION_OFFSET + 1,
    ),  # 108021
    "Under New Management": HaloCeData(
        type="Chapter",
        level="Keyes",
        id=constants.KEYS_OFFSET + constants.CHAPTER_OFFSET + 1,
    ),  # 109011
    "Upstairs, Downstairs": HaloCeData(
        type="Chapter",
        level="Keyes",
        id=constants.KEYS_OFFSET + constants.CHAPTER_OFFSET + 2,
    ),  # 109012
    "The Captain": HaloCeData(
        type="Chapter",
        level="Keyes",
        id=constants.KEYS_OFFSET + constants.CHAPTER_OFFSET + 3,
    ),  # 109013
    "...And the Horse You Rode in On": HaloCeData(
        type="Chapter",
        level="The Maw",
        id=constants.MAW_OFFSET + constants.CHAPTER_OFFSET + 1,
    ),  # 110011
    "Light Fuse, Run Away": HaloCeData(
        type="Chapter",
        level="The Maw",
        id=constants.MAW_OFFSET + constants.CHAPTER_OFFSET + 2,
    ),  # 110012
    "Warning: Hitchhikers May Be Escaping Convicts": HaloCeData(
        type="Chapter",
        level="The Maw",
        id=constants.MAW_OFFSET + constants.CHAPTER_OFFSET + 3,
    ),  # 110013
    "Grunt Birthday Party Skull": HaloCeData(
        type="Skull",
        level="The Maw",
        id=constants.MAW_OFFSET + constants.SKULL_LOCATION_OFFSET + 1,
    ),  # 110021
}
