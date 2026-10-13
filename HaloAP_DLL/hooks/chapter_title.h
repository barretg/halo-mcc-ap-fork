#pragma once

#include "../pipe_client.h"

namespace haloap {

    bool InstallChapterTitleHook(PipeClient* pipe);
    void UninstallChapterTitleHook();

    // True if the hook was installed but its target no longer starts with MinHook's jump:
    // halo1.dll was unloaded and loaded again at the same address between two checks,
    // which drops every CE hook
    bool ChapterTitleHookWasReset();

}  // namespace haloap