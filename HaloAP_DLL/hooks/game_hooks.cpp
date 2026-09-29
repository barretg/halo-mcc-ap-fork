#include "game_hooks.h"
#include "../minhook/MinHook.h"
#include "../pattern_scan.h"
#include "../item_handler.h"
#include <windows.h>
#include <psapi.h>
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
        //   G_SKULL:<game>:<map>:<key>      a skull was picked up; key is the H2 flavor, or
        //                                   the H3 primary skull index (secondary: 100 + index)
        //
        // After a win, MCC would load the next mission, which may be locked. Instead the game
        // goes back to the menu, like quitting from the pause menu:
        //   H2, H3:    the next shell command MCC sends the engine (slot 3) is replaced with
        //              pause, teardown, resume, which is what the pause menu's quit sends. The
        //              same quit is used when a locked mission starts anyway.
        //   H4, Reach: the win sets a "game won" byte in the game globals before ending the
        //              game; MCC loads the next mission only if it's set, so it's cleared
        //              after the win function returns.

        enum class PostWin { ShellQuit, ClearWonFlag };

        struct SkullScript {
            const char* name;   // script function whose implementation awards the skull
            int keyBase;        // added to the skull argument to make the reported key
            bool playerArg;     // impl(player, skull) rather than impl(skull)
        };

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
            PostWin postWin;
            SkullScript skulls[2];      // name nullptr: unused
            const char* const* maps;    // H2/H3: maps in menu order, for the locked-mission guard
            int mapCount;
        };

        const char* const kH2Maps[] = {
            "00a_introduction", "01a_tutorial", "01b_spacestation", "03a_oldmombasa",
            "03b_newmombasa", "04a_gasgiant", "04b_floodlab", "05a_deltaapproach",
            "05b_deltatowers", "06a_sentinelwalls", "06b_floodzone", "07a_highcharity",
            "08a_deltacliffs", "07b_forerunnership", "08b_deltacontrol",
        };
        const char* const kH3Maps[] = {
            "005_intro", "010_jungle", "020_base", "030_outskirts", "040_voi", "050_floodvoi",
            "070_waste", "100_citadel", "110_hc", "120_halo", "130_epilogue",
        };

        // Patterns and RVAs from Docs/hook-map-h2-h3-h4-reach.md. The map RVAs are for the
        // current MCC build; a wrong one shows up as "[game] ... no map name" in the log.
        const GameDef kGames[] = {
            { 2, "halo2.dll",
              "40 57 48 83 EC 20 48 8B 05 ? ? ? ? 0F B7 F9", 0, ChapterKind::TitleIndex,
              "48 83 EC 28 E8 ? ? ? ? 84 C0 74 ? 48 8D 0D ? ? ? ?",
              0x15A0B0C, true, PostWin::ShellQuit,
              { { "ice_cream_flavor_stock", 0, false }, {} },
              kH2Maps, sizeof(kH2Maps) / sizeof(kH2Maps[0]) },
            { 3, "halo3.dll",
              "48 83 EC 28 8B 15 ? ? ? ? 45 33 C0", 0, ChapterKind::TitleIndex,
              "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 E8 ? ? ? ? 33 FF",
              0x20A9118, false, PostWin::ShellQuit,
              { { "campaign_metagame_award_primary_skull", 0, true },
                { "campaign_metagame_award_secondary_skull", 100, true } },
              kH3Maps, sizeof(kH3Maps) / sizeof(kH3Maps[0]) },
            { 4, "halo4.dll",
              "48 83 EC 28 8B 15 ? ? ? ? 45 33 DB 65 48 8B 04 25 58 00 00 00 44 8B D1", 0,
              ChapterKind::TitleIndex,
              "48 83 EC 28 E8 ? ? ? ? 84 C0 74 ? 8B 0D ? ? ? ? 65 48 8B 04 25 58 00 00 00 "
              "BA 40 00 00 00 48 8B 04 C8 48 8B 0C 02",
              0x2A30268, false, PostWin::ClearWonFlag, {}, nullptr, 0 },
            // Reach's chapter pattern is anchored inside the function, on the load of the TLS
            // index before the string_id store
            { 6, "haloreach.dll",
              "8B 15 ? ? ? ? 8B 00 65 48 8B 0C 25 58 00 00 00 41 B8 B0 05 00 00 48 8B 0C D1 "
              "4A 8B 14 01 8B CB 89 82 6C 01 00 00", 0x2E, ChapterKind::ReachStringId,
              "48 83 EC 28 44 8B D2 E8 ? ? ? ? 84 C0 74 ? 8B 0D ? ? ? ? 65 48 8B 04 25 58 00 00 00 "
              "BA 48 00 00 00",
              0x274DD70, false, PostWin::ClearWonFlag, {}, nullptr, 0 },
        };
        constexpr int kGameCount = sizeof(kGames) / sizeof(kGames[0]);

        typedef void (*TitleFn)(uint16_t index, float duration);
        typedef uint64_t (*Passthrough4Fn)(uint64_t, uint64_t, uint64_t, uint64_t);
        typedef void (*ShellCommandFn)(void* engine, int type, void* context);

        struct GameState {
            HMODULE module = nullptr;
            HMODULE hookedModule = nullptr;  // module the targets below are in
            void* chapterTarget = nullptr;
            void* wonTarget = nullptr;
            void* chapterOriginal = nullptr;
            void* wonOriginal = nullptr;
            const uint32_t* reachTlsIndex = nullptr;
            char startedMap[64] = {};   // map a G_START was sent for since the DLL loaded

            void* skullTarget[2] = {};
            void* skullOriginal[2] = {};

            // ShellQuit
            void** engineGlobal = nullptr;
            void* shellTarget = nullptr;
            void* shellOriginal = nullptr;
            std::atomic<bool> quitPending{ false };

            // ClearWonFlag: the won byte is at [[TLS block][wonSlot]] + wonFlag
            const uint32_t* wonTlsIndex = nullptr;
            uint32_t wonSlot = 0;
            uint32_t wonFlag = 0;
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

        void ReportSkull(int gi, int key)
        {
            char map[64];
            if (!ReadMapName(gi, map, sizeof(map)))
            {
                printf("[game] %s: skull %d picked up, but no map name\n", kGames[gi].dll, key);
                return;
            }
            Send("G_SKULL:" + std::to_string(kGames[gi].code) + ":" + map + ":" + std::to_string(key));
        }

        // Clears the "game won" byte (H4, Reach); runs on the game thread, in the win's TLS
        void ClearWonFlag(int gi)
        {
            GameState& st = g_state[gi];
            if (!st.wonTlsIndex || !st.wonFlag) return;
            __try
            {
                uint8_t** tlsArray = (uint8_t**)__readgsqword(0x58);
                uint8_t* block = tlsArray[*st.wonTlsIndex];
                uint8_t* globals = *(uint8_t**)(block + st.wonSlot);
                globals[st.wonFlag] = 0;
                printf("[game] %s: won flag cleared, returning to the menu\n", kGames[gi].dll);
            }
            __except (1) { printf("[game] %s: couldn't clear the won flag\n", kGames[gi].dll); }
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
            uint64_t result = original ? original(a, b, c, d) : 0;
            if (kGames[GI].postWin == PostWin::ClearWonFlag)
                ClearWonFlag(GI);
            else
                g_state[GI].quitPending.store(true);
            return result;
        }

        template <int GI>
        void DetourShell(void* engine, int type, void* context)
        {
            auto original = (ShellCommandFn)g_state[GI].shellOriginal;
            if (!original) return;
            if (g_state[GI].quitPending.exchange(false))
            {
                printf("[game] %s: shell command 0x%x replaced with quit to menu\n", kGames[GI].dll, type);
                original(engine, 0x0, nullptr);  // pause
                original(engine, 0xD, nullptr);  // teardown
                original(engine, 0x1, nullptr);  // resume
                return;
            }
            original(engine, type, context);
        }

        template <int GI, int K>
        uint64_t DetourSkull(uint64_t a, uint64_t b, uint64_t c, uint64_t d)
        {
            const SkullScript& script = kGames[GI].skulls[K];
            // H3 awards to player0..3; the missing players are NONE
            if (!script.playerArg)
                ReportSkull(GI, script.keyBase + (int32_t)a);
            else if ((uint32_t)a != 0xFFFFFFFF)
                ReportSkull(GI, script.keyBase + (int16_t)b);
            auto original = (Passthrough4Fn)g_state[GI].skullOriginal[K];
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

        void* ShellDetourFor(int gi)
        {
            switch (gi)
            {
            case 0: return (void*)&DetourShell<0>;
            case 1: return (void*)&DetourShell<1>;
            case 2: return (void*)&DetourShell<2>;
            case 3: return (void*)&DetourShell<3>;
            }
            return nullptr;
        }

        void* SkullDetourFor(int gi, int k)
        {
            switch (gi * 2 + k)
            {
            case 0: return (void*)&DetourSkull<0, 0>;
            case 1: return (void*)&DetourSkull<0, 1>;
            case 2: return (void*)&DetourSkull<1, 0>;
            case 3: return (void*)&DetourSkull<1, 1>;
            case 4: return (void*)&DetourSkull<2, 0>;
            case 5: return (void*)&DetourSkull<2, 1>;
            case 6: return (void*)&DetourSkull<3, 0>;
            case 7: return (void*)&DetourSkull<3, 1>;
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

        bool InModule(HMODULE module, const void* p)
        {
            MODULEINFO mi = {};
            if (!GetModuleInformation(GetCurrentProcess(), module, &mi, sizeof(mi))) return false;
            return p >= mi.lpBaseOfDll && (const uint8_t*)p < (const uint8_t*)mi.lpBaseOfDll + mi.SizeOfImage;
        }

        // A script function's implementation, found through its definition: the definition
        // holds a pointer to the function's name and, 0x18 bytes on, its evaluator; the
        // evaluator reads the arguments and calls the implementation right after "mov ecx, [rax]".
        void* FindScriptImpl(HMODULE module, const char* name)
        {
            MODULEINFO mi = {};
            if (!GetModuleInformation(GetCurrentProcess(), module, &mi, sizeof(mi))) return nullptr;
            uint8_t* base = (uint8_t*)mi.lpBaseOfDll;
            size_t size = mi.SizeOfImage;
            size_t len = strlen(name) + 1;

            __try
            {
                uint8_t* str = nullptr;
                for (size_t i = 1; i + len < size && !str; i++)
                    if (base[i] == (uint8_t)name[0] && base[i - 1] == 0 && memcmp(base + i, name, len) == 0)
                        str = base + i;
                if (!str) return nullptr;

                uint8_t* evaluator = nullptr;
                for (size_t i = 0; i + 0x20 <= size && !evaluator; i += 8)
                    if (*(uint8_t**)(base + i) == str)
                        evaluator = *(uint8_t**)(base + i + 0x18);
                if (!evaluator || evaluator < base || evaluator >= base + size) return nullptr;

                for (int i = 0; i < 0x30; i++)
                    if (evaluator[i] == 0x8B && evaluator[i + 1] == 0x08 && evaluator[i + 2] == 0xE8)
                    {
                        uint8_t* impl = evaluator + i + 7 + *(int32_t*)(evaluator + i + 3);
                        return (impl >= base && impl < base + size) ? impl : nullptr;
                    }
            }
            __except (1) {}
            return nullptr;
        }

        // The global CreateGameEngine stores the engine object in: the last
        // "mov [rip + disp32], r64" in the export (as for CE; see shell_level_load.cpp)
        void** FindEngineGlobal(HMODULE module)
        {
            uint8_t* create = (uint8_t*)GetProcAddress(module, "CreateGameEngine");
            if (!create) return nullptr;
            void** found = nullptr;
            __try
            {
                for (int i = 0; i < 1024; i++)
                    if (create[i] == 0x48 && create[i + 1] == 0x89 && (create[i + 2] & 0xC7) == 0x05)
                        found = (void**)(create + i + 7 + *(int32_t*)(create + i + 3));
            }
            __except (1) { return nullptr; }
            return (found && InModule(module, found)) ? found : nullptr;
        }

        // H4 / Reach win functions: "mov ecx, [rip + tls_index]", "mov rax, gs:[58h]",
        // "mov edx, slot", ..., "mov byte ptr [rcx + won], 1"
        bool ParseWonFlag(uint8_t* fn, GameState& st)
        {
            static const uint8_t kGsLoad[] = { 0x65, 0x48, 0x8B, 0x04, 0x25, 0x58, 0x00, 0x00, 0x00 };
            __try
            {
                for (int i = 0; i < 0x30 && !st.wonTlsIndex; i++)
                    if (fn[i] == 0x8B && fn[i + 1] == 0x0D)
                        st.wonTlsIndex = (const uint32_t*)(fn + i + 6 + *(int32_t*)(fn + i + 2));
                for (int i = 0; i < 0x40 && !st.wonSlot; i++)
                    if (memcmp(fn + i, kGsLoad, sizeof(kGsLoad)) == 0 && fn[i + 9] == 0xBA)
                        st.wonSlot = *(uint32_t*)(fn + i + 10);
                for (int i = 0; i < 0x60 && !st.wonFlag; i++)
                    if (fn[i] == 0xC6 && fn[i + 1] == 0x81 && fn[i + 6] == 0x01)
                        st.wonFlag = *(uint32_t*)(fn + i + 2);
            }
            __except (1) {}
            return st.wonTlsIndex && st.wonSlot && st.wonFlag;
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
            DropHook(st.skullTarget[0], st.skullOriginal[0], sameModule);
            DropHook(st.skullTarget[1], st.skullOriginal[1], sameModule);
            DropHook(st.shellTarget, st.shellOriginal, sameModule);
            st.hookedModule = module;
            st.engineGlobal = nullptr;
            st.quitPending.store(false);
            st.wonTlsIndex = nullptr;
            st.wonSlot = st.wonFlag = 0;
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

            if (def.postWin == PostWin::ClearWonFlag)
            {
                if (!wonTarget || !ParseWonFlag((uint8_t*)wonTarget, st))
                    printf("[game] %s: won flag not found; a win will load the next mission\n", def.dll);
            }
            else
            {
                st.engineGlobal = FindEngineGlobal(module);
                if (!st.engineGlobal)
                    printf("[game] %s: engine global not found; a win will load the next mission\n", def.dll);
            }

            for (int k = 0; k < 2; k++)
            {
                if (!def.skulls[k].name) continue;
                void* impl = FindScriptImpl(module, def.skulls[k].name);
                if (!impl)
                    printf("[game] %s: %s not found\n", def.dll, def.skulls[k].name);
                else if (Hook(def.skulls[k].name, def.dll, impl, SkullDetourFor(gi, k), &st.skullOriginal[k]))
                    st.skullTarget[k] = impl;
            }
        }

        // The engine object only exists once MCC has created it, so the shell command hook
        // goes in on a later tick. Its vtable (and so slot 3) is fixed for the DLL's lifetime.
        void TryHookShell(int gi)
        {
            GameState& st = g_state[gi];
            if (st.shellTarget || !st.engineGlobal) return;
            void* target = nullptr;
            __try
            {
                void* engine = *st.engineGlobal;
                if (!engine) return;
                target = (*(void***)engine)[3];
            }
            __except (1) { return; }
            if (!InModule(st.module, target)) return;
            if (Hook("shell command", kGames[gi].dll, target, ShellDetourFor(gi), &st.shellOriginal))
                st.shellTarget = target;
            else
                st.engineGlobal = nullptr;  // don't retry every tick
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

        for (int gi = 0; gi < kGameCount; gi++)
            if (g_state[gi].module && kGames[gi].postWin == PostWin::ShellQuit)
                TryHookShell(gi);

        // In a mission only the game being played stays loaded (at the menu they all are).
        // Report its mission start once the map name is there.
        int loaded = 0;
        for (int gi = 0; gi < kGameCount; gi++)
            if (g_state[gi].module) loaded++;
        if (loaded != 1)
            return;

        for (int gi = 0; gi < kGameCount; gi++)
        {
            GameState& st = g_state[gi];
            if (!st.module) continue;
            char map[64];
            if (!ReadMapName(gi, map, sizeof(map))) continue;
            if (strcmp(map, st.startedMap) == 0) continue;
            strncpy_s(st.startedMap, map, _TRUNCATE);
            Send("G_START:" + std::to_string(kGames[gi].code) + ":" + map);

            // The menus hide locked missions and a win goes back to the menu, so this is only
            // a backstop: a locked mission that starts anyway is quit on the next shell command
            for (int i = 0; i < kGames[gi].mapCount; i++)
                if (_stricmp(kGames[gi].maps[i], map) == 0 &&
                    !GetItemHandler().isMissionAllowed(kGames[gi].code, i))
                {
                    printf("[game] %s: %s is locked, quitting to the menu\n", kGames[gi].dll, map);
                    st.quitPending.store(true);
                }
        }
    }

}  // namespace haloap
