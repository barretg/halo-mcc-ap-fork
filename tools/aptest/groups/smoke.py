"""One mission per game: the hooks fire and their checks arrive."""

from __future__ import annotations

from scenario import Group, Scenario

# A mission per game that's neither cinematic nor the final, with a chapter card
PICKS = {"ce": "The Truth and Reconciliation", "h2a": "Metropolis", "h3": "The Storm",
         "h4": "Requiem", "reach": "Winter Contingency"}


def build(ctx) -> list[Scenario]:
    out: list[Scenario] = []
    for game, name in PICKS.items():
        m = ctx.mission(game, name)
        if m.start_location:
            out.append(Scenario(
                title=f"{m.level}: starting the mission sends Mission Start",
                mission=m, expect=[m.start_location], auto=True, steps="Nothing to do."))
        chapter = m.chapters[-1]
        out.append(Scenario(
            title=f"{m.level}: a chapter card sends its check",
            mission=m, commands=[f"/title {chapter.keys[0]}"], expect=[chapter.location], auto=True,
            steps=f"The harness shows '{chapter.name}'; nothing to do."))
        out.append(Scenario(
            title=f"{m.level}: winning sends the mission and its chapters, then the menu",
            mission=m, commands=["/win"],
            expect=[m.completion] + [c.location for c in m.chapters] +
                   ([m.start_location] if m.start_location else []),
            steps="The harness wins the mission. The game should go back to the menu and not "
                  "start the next mission (not even briefly). pass or fail <what happened>."))

    # A real win, not /win: the cutscene-only missions win by themselves at the end
    for game in ("h2a", "h3", "h4", "reach"):
        m = next(m for m in ctx.games[game] if m.cinematic)
        after = ctx.games[game][m.number]  # the mission MCC would go on to (locked)
        out.append(Scenario(
            title=f"{m.level}: its real win goes back to the menu",
            mission=m, expect=[m.completion], locked=[after.level],
            steps=f"Watch (or skip) the cutscene to the end. The mission completes, and the game "
                  f"should go back to the menu, not on to {after.name}. pass or fail."))
    return out


GROUP = Group("smoke", "a chapter card and a win in each game", build)
