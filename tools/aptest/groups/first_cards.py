"""Fully automatic: load every mission and wait for its first chapter card's check,
without commands. Shows the hooks fire on their own. Don't skip cutscenes."""

from __future__ import annotations

from scenario import Group, Scenario


def build(ctx) -> list[Scenario]:
    out: list[Scenario] = []
    for game, missions in ctx.games.items():
        for m in missions:
            expect = ([m.start_location] if m.start_location else []) + \
                     ([m.chapters[0].location] if m.chapters else [])
            if not expect:
                continue
            out.append(Scenario(
                title=f"{m.level}: the mission's first card arrives by itself",
                mission=m, expect=expect, auto=True, timeout=240,
                steps=f"Don't skip anything. Waiting for '{m.chapters[0].name if m.chapters else 'Mission Start'}' "
                      "(fails after 4 minutes; if the first card needs some play, play to it)."))
    return out


GROUP = Group("first_cards", "every mission's first card, by itself (automatic)", build)
