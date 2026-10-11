#pragma once

#include "../pipe_client.h"

namespace haloap {

    // Death Link for Halo CE (see deathlink.h); the other games' is in game_hooks.cpp
    bool InstallCeDeathLinkHook(PipeClient* pipe);
    void UninstallCeDeathLinkHook();

}  // namespace haloap
