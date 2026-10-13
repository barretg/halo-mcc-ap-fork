"""The reported bugs fixed on 2026-10-13: chapters missed on CE, cards in cutscenes."""

from __future__ import annotations

from scenario import Group, Scenario


def build(ctx) -> list[Scenario]:
    tr = ctx.mission("ce", "The Truth and Reconciliation")
    shut_up = tr.chapter("Shut up and get Behind me...Sir")
    library = ctx.mission("ce", "The Library")
    maw = ctx.mission("ce", "The Maw")
    storm = ctx.mission("h3", "The Storm")
    think_big = storm.chapter("Think Big")
    floodgate = ctx.mission("h3", "Floodgate")
    return [
        Scenario(
            title="CE The Library: its first card arrives",
            mission=library, expect=[library.chapters[0].location], auto=True, timeout=240,
            steps="Don't skip the intro. 'The Library' should arrive by itself."),
        Scenario(
            title="CE The Maw: its first card arrives, right after Keyes",
            mission=maw, expect=[maw.chapters[0].location], auto=True, timeout=240,
            steps="Don't skip the intro. '...And the Horse You Rode In On' should arrive, not a "
                  "Keyes chapter."),
        Scenario(
            title="CE T&R: watching Keyes's rescue sends 'Shut Up and Get Behind Me... Sir'",
            mission=tr, expect=[shut_up.location],
            steps="Play to Keyes's cell in the brig and watch the rescue cutscene without "
                  "skipping. The chapter should arrive during it. pass or fail."),
        Scenario(
            title="CE T&R: skipping the rescue, the win still sends the chapter",
            mission=tr, reload=True, commands=[], expect=[tr.completion, shut_up.location],
            steps="Play to the rescue cutscene and skip it: no chapter yet. Then type /win: "
                  "the mission and the chapter both arrive. pass or fail."),
        Scenario(
            title="CE The Maw: 'Warning: Hitchhikers' arrives at its own card",
            mission=maw, expect=[maw.chapter("Warning: Hitchhikers May Be Escaping Convicts").location],
            steps="Play to the 'Warning: Hitchhikers' card (the escape run). It should arrive "
                  "then, not at 'Light Fuse, Run Away'. pass or fail."),
        Scenario(
            title="H3 The Storm: 'Think Big' arrives when watched",
            mission=storm, expect=[think_big.location],
            steps="Play to the Scarab and watch its cutscene. 'Think Big' should arrive. pass or fail."),
        Scenario(
            title="H3 Floodgate: a locked mission goes back to the menu",
            mission=floodgate, locked=[floodgate.level],
            steps="Floodgate is locked. If you're in an H3 mission the harness loads it anyway; "
                  "otherwise pick it from the menu if it shows (it shouldn't). The game should "
                  "go back to the menu, and no Floodgate check arrive. pass or fail."),
    ]


GROUP = Group("fixes", "the 2026-10-13 bug reports", build)
