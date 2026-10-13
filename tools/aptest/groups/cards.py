"""Every chapter card: the title index the tables use shows the chapter it's mapped to.
One group per game (cards_ce, ...); `cards` runs them all."""

from __future__ import annotations

from scenario import Group, Scenario


def cards(game: str):
    def build(ctx) -> list[Scenario]:
        out: list[Scenario] = []
        for m in ctx.games[game]:
            for chapter in m.chapters:
                for key in chapter.keys:
                    note = ""
                    if len(chapter.keys) > 1:
                        note = (f" It's one of {len(chapter.keys)} titles for this card "
                                "(the text may be half the card, or vary with difficulty).")
                    out.append(Scenario(
                        title=f"{m.level}: title {key} is '{chapter.name}'",
                        mission=m, commands=[f"/title {key}"], expect=[chapter.location],
                        steps=f"A card should show '{chapter.name}'.{note} "
                              "pass, or fail <what it showed>."))
        return out
    return build


GROUP = Group("cards", "every chapter card shows its chapter", lambda ctx: [],
              includes=("cards_ce", "cards_h2", "cards_h3", "cards_h4", "cards_reach"))
