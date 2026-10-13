#include "mission_segment.h"
#include "mission_complete.h"
#include "../minhook/MinHook.h"
#include "../pattern_scan.h"
#include <cstdio>
#include <cstdint>
#include <cstring>

namespace haloap {

    namespace {
        // In the mcc_mission_segment script function (halo1+0xB1E258): the call that hands
        // the segment name to the reporter (halo1+0xAF75F4), which is the call at +0x1D.
        //   cmp qword ptr [host], 0 ; mov eax,[rax] ; mov [rsp+30h],eax ; je ;
        //   lea rcx,[rsp+30h] ; call <string from script string data> ; mov rcx,rax ; call <reporter>
        const char* kPattern =
            "48 83 3D ? ? ? ? 00 8B 00 89 44 24 30 74 ? 48 8D 4C 24 30 E8 ? ? ? ? 48 8B C8 E8";
        const size_t kCallOffset = 0x1D;

        typedef void (*MissionSegmentFn)(const char* segment);
        MissionSegmentFn g_original = nullptr;
        void* g_target = nullptr;
        PipeClient* g_pipe = nullptr;

        void DetourMissionSegment(const char* segment) {
            const char* mission = ReadCurrentMissionName();
            if (segment && g_pipe && g_pipe->IsConnected()) {
                char buf[160];
                snprintf(buf, sizeof(buf), "SEGMENT:%s:%.100s", mission ? mission : "?", segment);
                g_pipe->SendAsync(buf);
            }
            printf("[hook] mission segment: mission=%s segment=%s\n",
                mission ? mission : "?", segment ? segment : "(null)");
            if (g_original)
                g_original(segment);
        }
    }

    bool InstallMissionSegmentHook(PipeClient* pipe) {
        g_pipe = pipe;
        HMODULE halo1 = GetModuleHandleA("halo1.dll");
        if (!halo1) return false;

        uint8_t* match = (uint8_t*)FindPatternInModule(halo1, kPattern);
        if (!match) {
            printf("[hook] (mission_segment) pattern not found\n");
            return false;
        }
        uint8_t* call = match + kCallOffset;
        int32_t rel;
        memcpy(&rel, call + 1, sizeof(rel));
        void* target = call + 5 + rel;

        if (MH_CreateHook(target, (void*)DetourMissionSegment, (void**)&g_original) != MH_OK ||
            MH_EnableHook(target) != MH_OK) {
            printf("[hook] (mission_segment) couldn't hook %p\n", target);
            MH_RemoveHook(target);
            return false;
        }
        g_target = target;
        printf("[hook] (mission_segment) installed at %p\n", target);
        return true;
    }

    void UninstallMissionSegmentHook() {
        if (g_target) {
            MH_DisableHook(g_target);
            MH_RemoveHook(g_target);
            g_target = nullptr;
        }
        g_original = nullptr;
        g_pipe = nullptr;
    }

}  // namespace haloap
