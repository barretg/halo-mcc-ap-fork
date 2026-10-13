#pragma once

#include "../pipe_client.h"
#include <string>

namespace haloap {

    // Chapter, mission-start and mission-complete checks for Halo 2, Halo 3, Halo 4 and
    // Reach (CE has its own hooks). Call every monitor tick: installs a game's hooks when
    // its DLL (re)loads and reports the mission start once a mission is running.
    // See Docs/hook-map-h2-h3-h4-reach.md for where each hook comes from.
    void UpdateGameHooks(PipeClient* pipe);

    // Debug: asks the running game's engine to load a level (its path, e.g.
    // "levels\\a50\\a50"), through vtable slot 9 of the object CreateGameEngine makes.
    // That slot queues a level load in CE; in the other games it's assumed to be the same
    // MCC interface. False if no mission is running.
    bool DebugLoadLevel(const std::string& path);

}  // namespace haloap
