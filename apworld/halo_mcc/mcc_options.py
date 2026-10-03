from dataclasses import dataclass
from Options import PerGameCommonOptions, Toggle, Choice, Range


class SkullSanity(Choice):
    """
    Adds skull disabler items to the item pool. All included skulls are forced
    on at game start; receiving a "Disable X" item lets you toggle that skull off.

    off:         No skull items or logic.
    non_scoring: non scoring skulls are locked off, reciving the item for them lets you turn them on.
    all: All skulls are locked, scoring skulls are locked on and non scoring skulls are locked off. reciving the item for them lets you toggle them.
    inverted: all skulls are locked off, reciving the item for them lets you turn them on.
    """
    display_name = "Skull Sanity"
    option_off = 0
    option_non_scoring = 1
    option_all = 2
    option_inverted = 3
    default = 1


class SkullItemMode(Choice):
    """
    How skull items apply across games. Only matters with skullsanity on.

    per_game: each game gets its own skull items (e.g. "Halo 3: Iron Skull" only affects Halo 3).
    shared:   one item per skull (e.g. "Iron Skull") affects that skull in every game that has it.
    """
    display_name = "Skull Item Mode"
    option_per_game = 0
    option_shared = 1
    default = 0


class SkullsRequired(Range):
    """
    How many scoring skulls need to be disabled before mission completion is in logic
    only affects all option for skullsanity. Capped at the number of scoring skulls the
    mission's game has.
    """
    display_name = "Required Skull Disables"
    range_start = 0
    range_end = 17
    default = 8


# class Powerups(Toggle):
#    """Should Powerups be locations"""
#    display_name = "Enable Powerups"
#    default = True

class CeEnabled(Toggle):
    """Should CeEnabled be locations"""
    display_name = "Enable Halo CE"
    default = True


class CeFinalMission(Choice):
    """What the goal mission for halo CE is"""
    display_name = "Final CE Mission"
    default = 10
    option_pillar_of_autumn = 1
    option_halo = 2
    option_truth_and_reconciliation = 3
    option_silent_cartographer = 4
    option_assault_on_the_control_room = 5
    option_343_guilty_spark = 6
    option_library = 7
    option_two_betrayals = 8
    option_keyes = 9
    option_the_maw = 10
    option_random_choice = 11


class CeMissionsRequired(Range):
    """
    How many other Halo CE missions must be completed before the final CE mission opens.
    """
    display_name = "CE Missions Required for Final"
    range_start = 0
    range_end = 9
    default = 9

class H2Enabled(Toggle):
    """
    Include Halo 2 missions.
    """
    display_name = "Enable Halo 2"
    default = False


class H2FinalMission(Choice):
    """What the goal mission for Halo 2 is"""
    display_name = "Final Halo 2 Mission"
    option_the_armory = 2
    option_cairo_station = 3
    option_outskirts = 4
    option_metropolis = 5
    option_the_arbiter = 6
    option_the_oracle = 7
    option_delta_halo = 8
    option_regret = 9
    option_sacred_icon = 10
    option_quarantine_zone = 11
    option_gravemind = 12
    option_uprising = 13
    option_high_charity = 14
    option_the_great_journey = 15
    option_random_choice = 0
    default = 15


class H2MissionsRequired(Range):
    """
    How many other Halo 2 missions must be completed before the final Halo 2 mission opens.
    Capped at the number of other missions.
    """
    display_name = "Halo 2 Missions Required for Final"
    range_start = 0
    range_end = 14
    default = 14


class H3Enabled(Toggle):
    """
    Include Halo 3 missions.
    """
    display_name = "Enable Halo 3"
    default = False


class H3FinalMission(Choice):
    """What the goal mission for Halo 3 is"""
    display_name = "Final Halo 3 Mission"
    option_sierra_117 = 2
    option_crows_nest = 3
    option_tsavo_highway = 4
    option_the_storm = 5
    option_floodgate = 6
    option_the_ark = 7
    option_the_covenant = 8
    option_cortana = 9
    option_halo = 10
    option_random_choice = 0
    default = 10


class H3MissionsRequired(Range):
    """
    How many other Halo 3 missions must be completed before the final Halo 3 mission opens.
    Capped at the number of other missions.
    """
    display_name = "Halo 3 Missions Required for Final"
    range_start = 0
    range_end = 10
    default = 10


class H4Enabled(Toggle):
    """
    Include Halo 4 missions.
    """
    display_name = "Enable Halo 4"
    default = False


class H4FinalMission(Choice):
    """What the goal mission for Halo 4 is"""
    display_name = "Final Halo 4 Mission"
    option_dawn = 2
    option_requiem = 3
    option_forerunner = 4
    option_infinity = 5
    option_reclaimer = 6
    option_shutdown = 7
    option_composer = 8
    option_midnight = 9
    option_random_choice = 0
    default = 9


class H4MissionsRequired(Range):
    """
    How many other Halo 4 missions must be completed before the final Halo 4 mission opens.
    Capped at the number of other missions.
    """
    display_name = "Halo 4 Missions Required for Final"
    range_start = 0
    range_end = 9
    default = 9


class ReachEnabled(Toggle):
    """
    Include Halo Reach missions.
    """
    display_name = "Enable Halo Reach"
    default = False


class ReachFinalMission(Choice):
    """What the goal mission for Halo Reach is"""
    display_name = "Final Halo Reach Mission"
    option_winter_contingency = 2
    option_oni_sword_base = 3
    option_nightfall = 4
    option_tip_of_the_spear = 5
    option_long_night_of_solace = 6
    option_exodus = 7
    option_new_alexandria = 8
    option_the_package = 9
    option_the_pillar_of_autumn = 10
    option_lone_wolf = 11
    option_random_choice = 0
    default = 11


class ReachMissionsRequired(Range):
    """
    How many other Halo Reach missions must be completed before the final Halo Reach mission opens.
    Capped at the number of other missions.
    """
    display_name = "Halo Reach Missions Required for Final"
    range_start = 0
    range_end = 10
    default = 10


class H2SkullPickups(Toggle):
    """
    Picking up a Halo 2 skull in a mission is a location. Every Halo 2 skull except
    Blind (Outskirts) only spawns on Legendary.
    """
    display_name = "Halo 2 Skull Pickups"
    default = False


class H3SkullPickups(Toggle):
    """Picking up a Halo 3 skull in a mission is a location. Halo 3 skulls only spawn on Normal or harder."""
    display_name = "Halo 3 Skull Pickups"
    default = True


@dataclass
class MCCOptions(PerGameCommonOptions):
    skullsanity: SkullSanity
    skull_item_mode: SkullItemMode
    skulls_required: SkullsRequired
    # powerups: Powerups
    ce_enabled: CeEnabled
    ce_final_mission: CeFinalMission
    ce_missions_required: CeMissionsRequired
    h2_enabled: H2Enabled
    h2_final_mission: H2FinalMission
    h2_missions_required: H2MissionsRequired
    h3_enabled: H3Enabled
    h3_final_mission: H3FinalMission
    h3_missions_required: H3MissionsRequired
    h2_skull_pickups: H2SkullPickups
    h3_skull_pickups: H3SkullPickups
    h4_enabled: H4Enabled
    h4_final_mission: H4FinalMission
    h4_missions_required: H4MissionsRequired
    reach_enabled: ReachEnabled
    reach_final_mission: ReachFinalMission
    reach_missions_required: ReachMissionsRequired
