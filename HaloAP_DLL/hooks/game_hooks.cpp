#include "game_hooks.h"
#include "../minhook/MinHook.h"
#include "../pattern_scan.h"
#include <windows.h>
#include <intrin.h>
#include <atomic>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>

namespace haloap {

    namespace {

        // Messages to the launcher, which maps them to locations:
        //   G_START:<game>:<map>            a mission is running
        //   G_CHAPTER:<game>:<map>:<key>    a title card; key is the title index, or the
        //                                   chapter string_id for Reach
        //   G_COMPLETE:<game>:<map>         the mission was won

        enum class ChapterKind {
            TitleIndex,     // (short title_index[, float]): H2, H3, H4 cinematic_set_title
            ReachStringId,  // script fn chud_show_screen_chapter_title (string_id)
        };

        struct GameDef {
            int code;                   // apworld game code
            const char* dll;
            const char* chapterPattern;
            int chapterPatternOffset;   // function start = match - this
            ChapterKind chapterKind;
            const char* wonPattern;
            size_t mapRva;              // loaded map's name (or path, for H2) in the DLL
            bool mapIsPath;             // H2: "scenarios\solo\<map>\<map>"
        };

        // Patterns and RVAs from Docs/hook-map-h2-h3-h4-reach.md. The map RVAs are for the
        // current MCC build; a wrong one shows up as "[game] ... no map name" in the log.
        const GameDef kGames[] = {
            { 2, "halo2.dll",
              "40 57 48 83 EC 20 48 8B 05 ? ? ? ? 0F B7 F9", 0, ChapterKind::TitleIndex,
              "48 83 EC 28 E8 ? ? ? ? 84 C0 74 ? 48 8D 0D ? ? ? ?",
              0x15A0B0C, true },
            { 3, "halo3.dll",
              "48 83 EC 28 8B 15 ? ? ? ? 45 33 C0", 0, ChapterKind::TitleIndex,
              "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 E8 ? ? ? ? 33 FF",
              0x20A9118, false },
            { 4, "halo4.dll",
              "48 83 EC 28 8B 15 ? ? ? ? 45 33 DB 65 48 8B 04 25 58 00 00 00 44 8B D1", 0,
              ChapterKind::TitleIndex,
              "48 83 EC 28 E8 ? ? ? ? 84 C0 74 ? 8B 0D ? ? ? ? 65 48 8B 04 25 58 00 00 00 "
              "BA 40 00 00 00 48 8B 04 C8 48 8B 0C 02",
              0x2A30268, false },
            // Reach's chapter pattern is anchored inside the function, on the load of the TLS
            // index before the string_id store
            { 6, "haloreach.dll",
              "8B 15 ? ? ? ? 8B 00 65 48 8B 0C 25 58 00 00 00 41 B8 B0 05 00 00 48 8B 0C D1 "
              "4A 8B 14 01 8B CB 89 82 6C 01 00 00", 0x2E, ChapterKind::ReachStringId,
              "48 83 EC 28 44 8B D2 E8 ? ? ? ? 84 C0 74 ? 8B 0D ? ? ? ? 65 48 8B 04 25 58 00 00 00 "
              "BA 48 00 00 00",
              0x274DD70, false },
        };
        constexpr int kGameCount = sizeof(kGames) / sizeof(kGames[0]);

        typedef void (*TitleFn)(uint16_t index, float duration);
        typedef uint64_t (*Passthrough4Fn)(uint64_t, uint64_t, uint64_t, uint64_t);

        struct GameState {
            HMODULE module = nullptr;
            HMODULE hookedModule = nullptr;  // module the targets below are in
            void* chapterTarget = nullptr;
            void* wonTarget = nullptr;
            void* chapterOriginal = nullptr;
            void* wonOriginal = nullptr;
            const uint32_t* reachTlsIndex = nullptr;
            char startedMap[64] = {};   // map a G_START was sent for since the DLL loaded
        };

        GameState g_state[kGameCount];
        PipeClient* g_pipe = nullptr;

        void Send(const std::string& msg)
        {
            printf("[game] -> %s\n", msg.c_str());
            if (g_pipe && g_pipe->IsConnected())
                g_pipe->SendAsync(msg);
        }

        // The running mission's map name, or false if there isn't a valid one
        bool ReadMapName(int gi, char* out, size_t outSize)
        {
            const GameDef& def = kGames[gi];
            HMODULE module = g_state[gi].module;
            if (!module) return false;

            char raw[160] = {};
            __try { memcpy(raw, (const uint8_t*)module + def.mapRva, sizeof(raw) - 1); }
            __except (1) { return false; }

            const char* name = raw;
            if (def.mapIsPath)
            {
                const char* solo = strstr(raw, "\\solo\\");
                if (!solo) return false;
                name = solo + 6;
            }

            size_t n = 0;
            for (; n + 1 < outSize && name[n] && name[n] != '\\'; n++)
            {
                char c = name[n];
                bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_';
                if (!ok) return false;
                out[n] = c;
            }
            out[n] = 0;
            return n >= 2;
        }

        void ReportChapter(int gi, uint32_t key)
        {
            char map[64];
            if (!ReadMapName(gi, map, sizeof(map)))
            {
                printf("[game] %s: title %u shown, but no map name\n", kGames[gi].dll, key);
                return;
            }
            Send("G_CHAPTER:" + std::to_string(kGames[gi].code) + ":" + map + ":" + std::to_string(key));
        }

        void ReportWon(int gi)
        {
            char map[64];
            if (!ReadMapName(gi, map, sizeof(map)))
            {
                printf("[game] %s: mission won, but no map name\n", kGames[gi].dll);
                return;
            }
            Send("G_COMPLETE:" + std::to_string(kGames[gi].code) + ":" + map);
        }

        // One detour per game and hook, since each needs its own original
        template <int GI>
        void DetourTitle(uint16_t index, float duration)
        {
            ReportChapter(GI, index);
            auto original = (TitleFn)g_state[GI].chapterOriginal;
            if (original) original(index, duration);
        }

        template <int GI>
        uint64_t DetourWon(uint64_t a, uint64_t b, uint64_t c, uint64_t d)
        {
            ReportWon(GI);
            auto original = (Passthrough4Fn)g_state[GI].wonOriginal;
            return original ? original(a, b, c, d) : 0;
        }

        // Reach's chapter script function stores the string_id at
        // [TLS block + 0x5B0] + 0x16C; a changed, non-zero value after the call is a card
        // going up (the clear call stores 0 or nothing)
        uint32_t ReadReachChapterSlot(int gi)
        {
            const uint32_t* tlsIndex = g_state[gi].reachTlsIndex;
            if (!tlsIndex) return 0;
            __try
            {
                uint8_t** tlsArray = (uint8_t**)__readgsqword(0x58);
                uint8_t* block = tlsArray[*tlsIndex];
                uint8_t* slot = *(uint8_t**)(block + 0x5B0);
                return *(uint32_t*)(slot + 0x16C);
            }
            __except (1) { return 0; }
        }

        template <int GI>
        uint64_t DetourReachChapter(uint64_t a, uint64_t b, uint64_t c, uint64_t d)
        {
            uint32_t before = ReadReachChapterSlot(GI);
            auto original = (Passthrough4Fn)g_state[GI].chapterOriginal;
            uint64_t result = original ? original(a, b, c, d) : 0;
            uint32_t after = ReadReachChapterSlot(GI);
            if (after != 0 && after != before)
                ReportChapter(GI, after);
            return result;
        }

        template <int GI>
        void* ChapterDetour()
        {
            return kGames[GI].chapterKind == ChapterKind::ReachStringId
                ? (void*)&DetourReachChapter<GI> : (void*)&DetourTitle<GI>;
        }

        void* ChapterDetourFor(int gi)
        {
            switch (gi)
            {
            case 0: return ChapterDetour<0>();
            case 1: return ChapterDetour<1>();
            case 2: return ChapterDetour<2>();
            case 3: return ChapterDetour<3>();
            }
            return nullptr;
        }

        void* WonDetourFor(int gi)
        {
            switch (gi)
            {
            case 0: return (void*)&DetourWon<0>;
            case 1: return (void*)&DetourWon<1>;
            case 2: return (void*)&DetourWon<2>;
            case 3: return (void*)&DetourWon<3>;
            }
            return nullptr;
        }

        // Hooks on a DLL that was unloaded can't be disabled (the memory is gone), so
        // they're removed once the DLL is back. Only when it's back at the same base:
        // removing writes the saved original bytes, which then match. At a different base
        // the old address may belong to something else, so the stale entry is left alone.
        void DropHook(void*& target, void*& original, bool sameModule)
        {
            if (target && sameModule)
            {
                MH_DisableHook(target);
                MH_RemoveHook(target);
            }
            target = nullptr;
            original = nullptr;
        }

        bool Hook(const char* what, const char* dll, void* target, void* detour, void** original)
        {
            if (MH_CreateHook(target, detour, original) != MH_OK || MH_EnableHook(target) != MH_OK)
            {
                printf("[game] %s: %s hook at %p failed\n", dll, what, target);
                MH_RemoveHook(target);
                *original = nullptr;
                return false;
            }
            printf("[game] %s: %s hook installed at %p\n", dll, what, target);
            return true;
        }

        void InstallGame(int gi, HMODULE module)
        {
            const GameDef& def = kGames[gi];
            GameState& st = g_state[gi];
            bool sameModule = st.hookedModule == module;
            DropHook(st.chapterTarget, st.chapterOriginal, sameModule);
            DropHook(st.wonTarget, st.wonOriginal, sameModule);
            st.hookedModule = module;
            st.reachTlsIndex = nullptr;
            st.startedMap[0] = 0;
            st.module = module;

            uint8_t* chapterMatch = (uint8_t*)FindPatternInModule(module, def.chapterPattern);
            if (!chapterMatch)
                printf("[game] %s: chapter pattern not found\n", def.dll);
            else
            {
                if (def.chapterKind == ChapterKind::ReachStringId)
                {
                    // mov edx, [rip + disp32]: the TLS index variable
                    int32_t disp = *(int32_t*)(chapterMatch + 2);
                    st.reachTlsIndex = (const uint32_t*)(chapterMatch + 6 + disp);
                }
                void* target = chapterMatch - def.chapterPatternOffset;
                if (Hook("chapter", def.dll, target, ChapterDetourFor(gi), &st.chapterOriginal))
                    st.chapterTarget = target;
            }

            void* wonTarget = FindPatternInModule(module, def.wonPattern);
            if (!wonTarget)
                printf("[game] %s: mission-won pattern not found\n", def.dll);
            else if (Hook("mission-won", def.dll, wonTarget, WonDetourFor(gi), &st.wonOriginal))
                st.wonTarget = wonTarget;
        }
    }

    void UpdateGameHooks(PipeClient* pipe)
    {
        g_pipe = pipe;

        for (int gi = 0; gi < kGameCount; gi++)
        {
            HMODULE module = GetModuleHandleA(kGames[gi].dll);
            GameState& st = g_state[gi];
            if (module != st.module)
            {
                if (module)
                {
                    printf("[game] %s loaded at %p\n", kGames[gi].dll, module);
                    InstallGame(gi, module);
                }
                else
                {
                    printf("[game] %s unloaded\n", kGames[gi].dll);
                    st.module = nullptr;  // hooks are dropped when it comes back
                }
            }
        }

        // In a mission only the game being played stays loaded. Report its mission start
        // once the map name is there.
        for (int gi = 0; gi < kGameCount; gi++)
        {
            GameState& st = g_state[gi];
            if (!st.module) continue;
            char map[64];
            if (!ReadMapName(gi, map, sizeof(map))) continue;
            if (strcmp(map, st.startedMap) == 0) continue;
            strncpy_s(st.startedMap, map, _TRUNCATE);
            Send("G_START:" + std::to_string(kGames[gi].code) + ":" + map);
        }
    }

}  // namespace haloap
