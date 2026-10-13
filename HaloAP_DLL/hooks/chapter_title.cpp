#include "chapter_title.h"
#include "mission_complete.h"
#include "../minhook/MinHook.h"
#include "../pattern_scan.h"
#include "shared/common.h"
#include <cstdio>
#include <cstdint>

namespace haloap {

    namespace {
        const char* kPattern =
            "4c 8b 05 ? ? ? ? 44 0f b7 c9 33 d2 48 0f bf c2 66 41 83 7c 80 0e ff";

        typedef void (*CinematicSetTitleFn)(uint16_t titleIndex, float duration);
        CinematicSetTitleFn g_originalSetTitle = nullptr;
        void* g_hookTarget = nullptr;
        PipeClient* g_pipe = nullptr;

        void DetourCinematicSetTitle(uint16_t titleIndex, float duration) {
            // The mission is read now rather than taken from the last mission load, which
            // the launcher can miss (the load hook goes in up to a tick after halo1.dll)
            const char* mission = ReadCurrentMissionName();
            printf("[hook] Chapter title shown: mission=%s index=%d\n",
                mission ? mission : "?", titleIndex);

            if (g_pipe && g_pipe->IsConnected()) {
                char buf[96];
                if (mission)
                    snprintf(buf, sizeof(buf), "CHAPTER:%s:%d", mission, titleIndex);
                else
                    snprintf(buf, sizeof(buf), "CHAPTER:%d", titleIndex);
                g_pipe->SendAsync(buf);
            }

            if (g_originalSetTitle)
                g_originalSetTitle(titleIndex, duration);
        }
    }

    bool InstallChapterTitleHook(PipeClient* pipe) {
        g_pipe = pipe;

        HMODULE halo1 = GetModuleHandleA("halo1.dll");
        if (!halo1) {
            printf("[hook] (chapter_title) halo1.dll not loaded yet\n");
            return false;
        }

        void* target = FindPatternInModule(halo1, kPattern);
        if (!target) {
            printf("[hook] (chapter_title) pattern not found\n");
            return false;
        }

        printf("[hook] (chapter_title) CinematicSetTitle found at %p\n", target);

        MH_STATUS status = MH_CreateHook(target, (void*)DetourCinematicSetTitle,
            (void**)&g_originalSetTitle);
        if (status != MH_OK) {
            printf("[hook] (chapter_title) MH_CreateHook failed: %d\n", status);
            return false;
        }

        status = MH_EnableHook(target);
        if (status != MH_OK) {
            printf("[hook] (chapter_title) MH_EnableHook failed: %d\n", status);
            MH_RemoveHook(target);
            return false;
        }

        // Set only once it's in, so ChapterTitleHookWasReset never sees a failed install
        g_hookTarget = target;
        printf("[hook] (chapter_title) installed.\n");
        return true;
    }

    bool ChapterTitleHookWasReset() {
        if (!g_hookTarget) return false;
        __try { return *(const uint8_t*)g_hookTarget != 0xE9; }
        __except (1) { return true; }
    }

    void UninstallChapterTitleHook() {
        if (g_hookTarget) {
            MH_DisableHook(g_hookTarget);
            MH_RemoveHook(g_hookTarget);
            g_hookTarget = nullptr;
        }
        g_originalSetTitle = nullptr;
        g_pipe = nullptr;
    }

}  // namespace haloap