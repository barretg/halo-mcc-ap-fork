"""The reported bugs fixed on 2026-10-13: chapters missed on CE, cards in skippable
cutscenes (sent when the mission loads, or at the cutscene's mission segment), and the
cards a mission only shows sometimes."""

from __future__ import annotations

from scenario import Group, Scenario


def build(ctx) -> list[Scenario]:
    tr = ctx.mission("ce", "The Truth and Reconciliation")
    shut_up = tr.chapter("Shut up and get Behind me...Sir")
    library = ctx.mission("ce", "The Library")
    maw = ctx.mission("ce", "The Maw")
    belly = tr.chapter("Into the Belly of the Beast")
    pillar = ctx.mission("ce", "The Pillar of Autumn")
    reveille = pillar.chapter("Reveille")
    covenant = ctx.mission("h3", "The Covenant")
    trident = covenant.chapter("Trident")
    storm = ctx.mission("h3", "The Storm")
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
            title="CE T&R: skipping the gravity lift cutscene still sends 'Into the Belly of the Beast'",
            mission=tr, reload=True, expect=[belly.location],
            steps="Play to the gravity lift and skip its cutscene. The chapter should arrive as "
                  "the cutscene starts. pass or fail."),
        Scenario(
            title="CE T&R: skipping the rescue still sends 'Shut Up and Get Behind Me... Sir'",
            mission=tr, reload=True, expect=[shut_up.location],
            steps="Play to Keyes's cell and skip the rescue cutscene. The chapter should arrive "
                  "as the cutscene starts. pass or fail."),
        Scenario(
            title="CE The Pillar of Autumn: 'Reveille' arrives on load, on any difficulty",
            mission=pillar, reload=True, expect=[reveille.location], auto=True, timeout=60,
            steps="Start it on Heroic or Legendary if you can (the card itself only shows solo "
                  "on Normal). 'Reveille' should arrive as the mission loads."),
        Scenario(
            title="H3 The Covenant: 'Trident' arrives on load",
            mission=covenant, expect=[trident.location], auto=True, timeout=60,
            steps="Skip the intro if you like: 'Trident' arrives as the mission loads."),
        Scenario(
            title="CE The Maw: 'Warning: Hitchhikers' arrives at its own card",
            mission=maw, expect=[maw.chapter("Warning: Hitchhikers May Be Escaping Convicts").location],
            steps="Play to the 'Warning: Hitchhikers' card (the escape run). It should arrive "
                  "then, not at 'Light Fuse, Run Away'. pass or fail."),
        Scenario(
            title="H3 The Storm: the Scarab card is 'Judgment'",
            mission=storm, expect=[storm.chapter("Judgment").location],
            steps="Play to the Scarab. Its card reads 'Judgment', and that chapter arrives. "
                  "('Think Big' was a cut title and is no longer a location.) pass or fail."),
        Scenario(
            title="H3 Floodgate: a locked mission goes back to the menu",
            mission=floodgate, locked=[floodgate.level],
            steps="Floodgate is locked. If you're in an H3 mission the harness loads it anyway; "
                  "otherwise pick it from the menu if it shows (it shouldn't). The game should "
                  "go back to the menu, and no Floodgate check arrive. pass or fail."),
    ]


GROUP = Group("fixes", "the 2026-10-13 bug reports", build)
