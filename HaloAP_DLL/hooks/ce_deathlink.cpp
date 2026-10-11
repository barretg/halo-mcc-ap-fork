#include "ce_deathlink.h"
#include "../minhook/MinHook.h"
#include "../pattern_scan.h"
#include "../deathlink.h"
#include <cstdio>
#include <cstdint>

namespace haloap {

    namespace {
        // The players update, which the world update calls once per tick. Near its end it
        // checks the players' "all dead" flag; when it's set it asks for a revert to the
        // last checkpoint and sets a latch, which it clears again on any tick someone is
        // alive. The latch's 0 -> 1 edge is a death (in co-op, a full wipe). A received
        // link is applied from the same hook, so the kill runs on the game thread.
        // All live-verified on 2026-10-10.
        const char* kUpdatePattern =
            "48 8B C4 48 89 58 08 48 89 70 10 48 89 78 18 55 41 54 41 55 41 56 41 57 "
            "48 8D 68 A1 48 81 EC 00 01 00 00 48 8B 1D ? ? ? ? 45 33 ED";

        // In the players update: revert requests, then "mov [latch], r15b"
        const char* kLatchPattern =
            "44 88 2D ? ? ? ? 44 88 3D ? ? ? ? 44 88 3D ? ? ? ? EB ? 44 88 2D";

        // players(): the players array global, its datum size, data offset and unit
        // field, and its next-datum iterator
        const char* kPlayersPattern =
            "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 E8 ? ? ? ? 8B D8 83 F8 FF 74 ? "
            "48 8B 35 ? ? ? ? 83 CA FF EB ? 0F B7 D7 48 69 CA ? ? ? ? 48 63 56 ? 48 03 CE "
            "8B 54 0A ? 83 FA FF 74 ? 8B CB E8 ? ? ? ? 8B D7 48 8B CE E8 ? ? ? ?";

        // unit_kill's evaluator: object = get(unit, type 3), then its flags |= 0x20
        const char* kKillPattern =
            "8B 08 BA 03 00 00 00 E8 ? ? ? ? 48 85 C0 74 ? 66 83 88 ? ? 00 00 20";

        constexpr int kGameCode = 1;
        constexpr uint32_t kNone = 0xFFFFFFFF;

        typedef void (*UpdateFn)();
        typedef int32_t (*NextDatumFn)(void* array, int32_t index);
        typedef uint8_t* (*GetObjectFn)(uint32_t handle, int type);

        UpdateFn g_originalUpdate = nullptr;
        void* g_hookTarget = nullptr;
        PipeClient* g_pipe = nullptr;

        const uint8_t* g_latch = nullptr;
        uint8_t** g_players = nullptr;
        uint32_t g_playerSize = 0;
        uint8_t g_dataAt = 0, g_unitAt = 0;
        NextDatumFn g_nextDatum = nullptr;
        GetObjectFn g_getObject = nullptr;
        uint32_t g_killFlagsAt = 0;

        template <typename T>
        T* RipTarget(uint8_t* match, int at)
        {
            return (T*)(match + at + 4 + *(int32_t*)(match + at));
        }

        bool LatchSet()
        {
            __try { return g_latch && *g_latch != 0; }
            __except (1) { return false; }
        }

        // Kills every living player the way unit_kill does; runs on the game thread
        bool KillPlayers()
        {
            if (!g_players || !g_getObject)
            {
                printf("[deathlink] halo1.dll: no way to kill the player, dropped\n");
                return false;
            }
            int killed = 0;
            __try
            {
                uint8_t* players = *g_players;
                if (!players) return false;
                uint8_t* data = players + *(int32_t*)(players + g_dataAt);
                for (int32_t i = g_nextDatum(players, -1); i != -1; i = g_nextDatum(players, i))
                {
                    uint32_t unit = *(uint32_t*)(data + (i & 0xFFFF) * g_playerSize + g_unitAt);
                    if (unit == kNone) continue;
                    uint8_t* object = g_getObject(unit, 3);
                    if (!object) continue;
                    *(uint16_t*)(object + g_killFlagsAt) |= 0x20;
                    killed++;
                }
            }
            __except (1) { printf("[deathlink] halo1.dll: kill faulted\n"); }
            if (!killed)
                printf("[deathlink] halo1.dll: no living player, dropped\n");
            return killed > 0;
        }

        void DetourUpdate()
        {
            bool before = LatchSet();
            if (TakeDeathLinkKill())
            {
                if (before)
                    printf("[deathlink] halo1.dll: player already dead, dropped\n");
                else if (KillPlayers())
                    NoteDeathLinkKill(kGameCode);
            }
            if (g_originalUpdate) g_originalUpdate();
            if (!before && LatchSet())
                ReportDeath(g_pipe, kGameCode);
        }
    }

    bool InstallCeDeathLinkHook(PipeClient* pipe) {
        g_pipe = pipe;

        HMODULE halo1 = GetModuleHandleA("halo1.dll");
        if (!halo1) return false;

        uint8_t* latch = (uint8_t*)FindPatternInModule(halo1, kLatchPattern);
        void* target = FindPatternInModule(halo1, kUpdatePattern);
        if (!latch || !target) {
            printf("[hook] (ce_deathlink) %s pattern not found; deaths won't be sent\n",
                   latch ? "players update" : "latch");
            return false;
        }
        g_latch = RipTarget<const uint8_t>(latch, 17);

        if (uint8_t* p = (uint8_t*)FindPatternInModule(halo1, kPlayersPattern)) {
            g_players = RipTarget<uint8_t*>(p, 30);
            g_playerSize = *(uint32_t*)(p + 45);
            g_dataAt = p[52];
            g_unitAt = p[59];
            g_nextDatum = (NextDatumFn)RipTarget<uint8_t>(p, 78);
        }
        if (uint8_t* k = (uint8_t*)FindPatternInModule(halo1, kKillPattern)) {
            g_getObject = (GetObjectFn)RipTarget<uint8_t>(k, 8);
            g_killFlagsAt = *(uint32_t*)(k + 20);
        }
        if (!g_players || !g_getObject)
            printf("[hook] (ce_deathlink) %s not found; links can't kill\n",
                   g_players ? "unit_kill" : "player lookup");

        if (MH_CreateHook(target, (void*)DetourUpdate, (void**)&g_originalUpdate) != MH_OK ||
            MH_EnableHook(target) != MH_OK) {
            printf("[hook] (ce_deathlink) hook failed\n");
            MH_RemoveHook(target);
            g_originalUpdate = nullptr;
            return false;
        }
        g_hookTarget = target;
        printf("[hook] (ce_deathlink) installed at %p\n", target);
        return true;
    }

    void UninstallCeDeathLinkHook() {
        if (g_hookTarget) {
            MH_DisableHook(g_hookTarget);
            MH_RemoveHook(g_hookTarget);
            g_hookTarget = nullptr;
        }
        g_originalUpdate = nullptr;
        g_latch = nullptr;
        g_players = nullptr;
        g_nextDatum = nullptr;
        g_getObject = nullptr;
        g_pipe = nullptr;
    }

}  // namespace haloap
