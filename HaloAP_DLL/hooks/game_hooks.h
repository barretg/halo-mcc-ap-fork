#pragma once

#include "../pipe_client.h"

namespace haloap {

    // Chapter, mission-start and mission-complete checks for Halo 2, Halo 3, Halo 4 and
    // Reach (CE has its own hooks). Call every monitor tick: installs a game's hooks when
    // its DLL (re)loads and reports the mission start once a mission is running.
    // See Docs/hook-map-h2-h3-h4-reach.md for where each hook comes from.
    void UpdateGameHooks(PipeClient* pipe);

}  // namespace haloap
