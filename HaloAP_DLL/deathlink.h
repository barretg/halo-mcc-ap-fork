#pragma once

#include <string>

class PipeClient;

namespace haloap {

    // Death Link, DLL side. The launcher decides what goes out (amnesty, own bounces); the
    // DLL kills the players for a received link and tells natural deaths apart from
    // the ones it caused:
    //   launcher -> DLL  "DEATHLINK: <source>"   kill every player
    //   DLL -> launcher  "G_DEATH:<game>"         all players died (in co-op, a full wipe)
    //                    "G_DEATH_LINKED:<game>"  they died from a received link
    //
    // Kills and deaths are both handled on the game thread, from each game's hooks.

    // A Death Link came in (pipe thread). It's dropped if no game takes it in time,
    // e.g. at the menu.
    void RequestDeathLinkKill(const std::string& source);

    // Game thread: true once per request while it's still fresh. The caller kills the
    // players and calls NoteDeathLinkKill() if it did.
    bool TakeDeathLinkKill();
    void NoteDeathLinkKill(int game);

    // Game thread: all players died (the game's "lost" edge). Sends G_DEATH, or
    // G_DEATH_LINKED if a kill was applied just before.
    void ReportDeath(PipeClient* pipe, int game);

}  // namespace haloap
