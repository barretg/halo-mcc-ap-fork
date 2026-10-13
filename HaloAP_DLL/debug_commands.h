#pragma once

#include <string>

class PipeClient;

namespace haloap {

    // Debug commands, so hooks can be checked by loading a mission instead of playing it.
    // The launcher forwards them only when HALOAP_DEBUG is set:
    //   launcher -> DLL  "DEBUG: title <n>"   show title <n> (Reach: the chapter's string_id)
    //                    "DEBUG: win"         win the mission
    // CE, H2, H3 and H4 go through the hooked functions, so the hooks report them like the
    // real thing. Reach's chapter and win script functions do their work inline, so there
    // the DLL does the same work and reports it as the hooks would.
    // Like a Death Link they run on the game thread, from the hooks that run every tick.

    enum class DebugAction { None, Title, Win };

    // Pipe thread: parses "title <n>" / "win"; false if it isn't a known command
    bool RequestDebugAction(const std::string& command);

    // Game thread: the pending action, once, while it's still fresh
    DebugAction TakeDebugAction(int& arg);

    // Where DebugReport sends to; set by the pipe client
    void SetDebugPipe(PipeClient* pipe);

    // A command's outcome: logged, and sent to the launcher as "DEBUG_RESULT: <text>"
    void DebugReport(const char* format, ...);

}  // namespace haloap
