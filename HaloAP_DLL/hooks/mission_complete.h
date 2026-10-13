#pragma once

#include "../pipe_client.h"

namespace haloap {

    // Installs the mission-complete hook. Call after MinHook is initialized
    // and the pipe client is connected (or at least constructed).
    // Returns true on success.
    bool InstallMissionCompleteHook(PipeClient* pipe);

    // Uninstalls the hook. Safe to call during shutdown.
    void UninstallMissionCompleteHook();

    // The running CE mission's name ("a10"), or nullptr if halo1.dll isn't loaded or the
    // name looks invalid. Points to a static buffer, valid until the next call.
    const char* ReadCurrentMissionName();

    // Debug (game thread): wins the mission through the hooked game_won
    bool DebugWinMission();

}