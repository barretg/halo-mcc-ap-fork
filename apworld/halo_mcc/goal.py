from rule_builder.rules import *

def set_goal(world):
    # Goal: reach the final mission of every enabled game
    world.set_completion_rule(And(*[CanReachEntrance(f"Menu -> {final}")
                                    for final in world.final_missions.values()]))
