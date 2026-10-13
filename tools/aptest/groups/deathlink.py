"""Death Link in each game, both ways."""

from __future__ import annotations

from scenario import Group, Scenario

from .smoke import PICKS


def build(ctx) -> list[Scenario]:
    out: list[Scenario] = []
    for game, name in PICKS.items():
        m = ctx.mission(game, name)
        out.append(Scenario(
            title=f"{m.level}: a received Death Link kills you",
            mission=m, commands=["/deathlink"],
            steps="The harness sends a Death Link once you're in. You should die, and the "
                  "launcher should say it died from a received link (not send one back). "
                  "pass or fail."))
        out.append(Scenario(
            title=f"{m.level}: dying sends a Death Link",
            mission=m,
            steps="Die (e.g. a grenade at your feet). The launcher should print "
                  "'[deathlink] sent: ...'. pass or fail."))
    return out


GROUP = Group("deathlink", "Death Link in and out, per game", build)
