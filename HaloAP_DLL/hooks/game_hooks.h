#pragma once

#include "../pipe_client.h"
#include <string>

namespace haloap {

    // Chapter, mission-start and mission-complete checks for Halo 2, Halo 3, Halo 4 and
    // Reach (CE has its own hooks). Call every monitor tick: installs a game's hooks when
    // its DLL (re)loads and reports the mission start once a mission is running.
    // See Docs/hook-map-h2-h3-h4-reach.md for where each hook comes from.
    void UpdateGameHooks(PipeClient* pipe);

    // Debug: runs a HaloScript expression in the running game, e.g. "(map_reset)".
    // Vtable slot 9 of the object CreateGameEngine makes queues a console line, which
    // the engine's command drain runs as script when it starts "HS: " (lines starting
    // "MPBOT: " go elsewhere, anything else is dropped; halo1+0x954F6). Same in all five
    // games. False if no mission is running.
    // Loading a mission this way isn't possible: MCC's builds stub out map_name and
    // game_start (their handlers just return) in every game.
    bool DebugRunScript(const std::string& expression);

}  // namespace haloap
