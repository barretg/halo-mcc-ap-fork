#include "game_hooks.h"
#include "../minhook/MinHook.h"
#include "../pattern_scan.h"
#include "../item_handler.h"
#include "../deathlink.h"
#include "../debug_commands.h"
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
        //   H2, H3:    the DLL sends the engine (slot 3) pause, teardown, resume, which is what
        //              the pause menu's quit sends. Slot 3 only queues the message for the
        //              engine thread, so it's sent right after the win (on the game thread) or
        //              from the tick. The same quit is used when a locked mission starts anyway.
        //              H2 starts loading the next mission from the win itself, before the quit
        //              lands, so its main loop's launch request is also dropped once after a
        //              win (DetourLaunch).
        //   H4, Reach: the win sets a "game won" byte in the game globals before ending the
        //              game; MCC loads the next mission only if it's set, so it's cleared
        //              after the win function returns.
        //
        // Death Link (see deathlink.h): the campaign update calls game_lost(all_players_dead)
        // every tick, and that sets a "lost" byte in the game globals once everyone is dead.
        // Its 0 -> 1 edge is a death, so in co-op only a full wipe counts; one player dying
        // and respawning doesn't. A received link kills every player from the same hook, so
        // the kill runs on the game thread. H2 inlines that check, so it hooks what runs on
        // the edge and gets its tick from the all-dead getter instead.

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

        enum class KillKind {
            None,
            UnitKill,   // H2, H3: unit_kill's implementation, (unit)
            UnitFlags,  // the function H4's and Reach's unit_kill call, (unit, 0, 1, 2, 0)
        };

        struct DeathDef {
            // H3, H4, Reach: game_lost(bool), and where in the match its TLS index (rip
            // disp32), globals slot (imm32) and lost byte (disp32) are
            const char* lostPattern;
            int lostTlsAt, lostSlotAt, lostFlagAt;
            const char* lostEdgePattern;    // H2: runs once the lost byte is set
            const char* tickPattern;        // H2: players-all-dead getter, called each tick
            KillKind kill;
            const char* killPattern;
            // The players' units: H2 players(), H3 player_get, Reach player_get bodies, or
            // H4's unit-of-the-n-th-player function
            const char* playerPattern;
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
            const char* launchPattern;  // H2: the main loop's "launch the pending map" request
            DeathDef death;
            // H3: the per-frame step that, after a win, asks MCC for the next mission and
            // starts it (returns true if it did)
            const char* advancePattern = nullptr;
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

        // game_lost(bool) in H3 and Reach, which compile it the same way
        const char* const kLostPatternH3Reach =
            "40 53 48 83 EC 20 44 8B 0D ? ? ? ? 45 33 DB BB ? 00 00 00 84 C9 0F 84 ? ? ? ? 65 48 8B "
            "04 25 58 00 00 00 4E 8B 14 C8 4D 8B 04 1A 45 38 98 ? ? ? ? 0F 85 ? ? ? ? F3 0F 10 05 "
            "? ? ? ? 41 C6 80 ? ? ? ? 01";

        // Patterns and RVAs from Docs/hook-map-h2-h3-h4-reach.md. The map RVAs are for the
        // current MCC build; a wrong one shows up as "[game] ... no map name" in the log.
        const GameDef kGames[] = {
            { 2, "halo2.dll",
              "40 57 48 83 EC 20 48 8B 05 ? ? ? ? 0F B7 F9", 0, ChapterKind::TitleIndex,
              "48 83 EC 28 E8 ? ? ? ? 84 C0 74 ? 48 8D 0D ? ? ? ?",
              0x15A0B0C, true, PostWin::ShellQuit,
              { { "ice_cream_flavor_stock", 0, false }, {} },
              kH2Maps, sizeof(kH2Maps) / sizeof(kH2Maps[0]),
              "B1 01 C6 05 ? ? ? ? 01 E9 ? ? ? ? CC CC 0F B6 05 ? ? ? ? C3",
              { nullptr, 0, 0, 0,
                "48 83 EC 28 80 3D ? ? ? ? 00 0F 84 ? ? ? ? 80 3D ? ? ? ? 00 74 ? E8 ? ? ? ?",
                "48 8B 05 ? ? ? ? 0F B6 40 04 C3",
                KillKind::UnitKill,
                "83 F9 FF 74 ? 53 48 83 EC 20 48 8B 05 ? ? ? ? 8B D9 48 8B 50 48 48 85 D2 74 ? "
                "4C 8D 04 02 EB ? 45 33 C0 0F B7 CB 48 8D 04 49 49 8D 0C 80 E8 ? ? ? ? 8B CB "
                "66 83 88 ? ? 00 00 20",
                "48 89 5C 24 08 57 48 83 EC 20 E8 ? ? ? ? 48 8B 0D ? ? ? ? BA FF FF FF FF 8B F8 "
                "E8 ? ? ? ? 8B D8 83 F8 FF 74 ? 0F 1F 80 00 00 00 00 48 8B 0D ? ? ? ? 48 8B 51 48 "
                "48 85 D2 74 ? 4C 8D 04 0A EB ? 45 33 C0 0F B7 D3 48 69 C2 ? ? ? ? 42 8B 54 00 ?" } },
            { 3, "halo3.dll",
              "48 83 EC 28 8B 15 ? ? ? ? 45 33 C0", 0, ChapterKind::TitleIndex,
              "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 E8 ? ? ? ? 33 FF",
              0x20A9118, false, PostWin::ShellQuit,
              { { "campaign_metagame_award_primary_skull", 0, true },
                { "campaign_metagame_award_secondary_skull", 100, true } },
              kH3Maps, sizeof(kH3Maps) / sizeof(kH3Maps[0]), nullptr,
              { kLostPatternH3Reach, 9, 17, 49, nullptr, nullptr,
                KillKind::UnitKill,
                "48 83 EC 28 83 F9 FF 74 ? 8B 15 ? ? ? ? 65 48 8B 04 25 58 00 00 00 41 B9 ? 00 00 00 "
                "48 8B 04 D0 0F B7 D1 4E 8B 0C 08 4C 8D 04 52 49 8B 41 48 4A 8B 54 C0 10 83 8A ? ? 00 00 40 E8",
                "44 8B 08 83 CA FF 65 48 8B 04 25 58 00 00 00 45 8B C3 8B 0D ? ? ? ? 41 BA ? 00 00 00 "
                "48 8B 04 C8 4D 8B 14 02 45 85 C0 78 ? 45 3B 42 ? 7D ? 41 8B 42 ? 41 0F AF C0 48 63 C8 "
                "49 03 4A ? 66 44 39 19 74 ? 45 85 C9 74 ? 41 FF C9 41 FF C0 41 83 F8 04 7D ? EB ? 8B 51 ?" },
              "40 55 48 8D AC 24 B0 00 FF FF B8 50 00 01 00 E8 ? ? ? ? 48 2B E0 48 C7 44 24 60 FE FF FF FF "
              "48 89 9C 24 78 00 01 00 0F 29 B4 24 40 00 01 00 33 DB" },
            { 4, "halo4.dll",
              "48 83 EC 28 8B 15 ? ? ? ? 45 33 DB 65 48 8B 04 25 58 00 00 00 44 8B D1", 0,
              ChapterKind::TitleIndex,
              "48 83 EC 28 E8 ? ? ? ? 84 C0 74 ? 8B 0D ? ? ? ? 65 48 8B 04 25 58 00 00 00 "
              "BA 40 00 00 00 48 8B 04 C8 48 8B 0C 02",
              0x2A30268, false, PostWin::ClearWonFlag, {}, nullptr, 0, nullptr,
              { "48 83 EC 28 44 8B 0D ? ? ? ? 45 33 D2 41 BB ? 00 00 00 84 C9 74 ? 65 48 8B 04 25 "
                "58 00 00 00 4A 8B 14 C8 4D 8B 04 13 45 38 90 ? ? ? ? 75 ? F3 0F 10 05 ? ? ? ? "
                "41 C6 80 ? ? ? ? 01", 7, 16, 44, nullptr, nullptr,
                KillKind::UnitFlags,
                "44 8B 15 ? ? ? ? 65 48 8B 04 25 58 00 00 00 41 BB ? 00 00 00 4A 8B 04 D0 4D 8B 14 03 "
                "4D 8B 5A 50 44 0F B7 D1 4B 8D 04 52 4D 8B 54 C3 10 41 8B 82 ? ? 00 00 83 C8 20",
                "48 83 EC 28 E8 ? ? ? ? 44 8B C8 83 C8 FF 44 3B C8 74 ? 8B 15 ? ? ? ? 65 48 8B 0C 25 "
                "58 00 00 00 41 B8 ? 00 00 00 48 8B 0C D1 4E 8B 04 01 41 0F B7 C9 48 69 D1 ? ? ? ? "
                "49 8B 40 ? 8B 44 10 ? 48 83 C4 28 C3" } },
            // Reach's chapter pattern is anchored inside the function, on the load of the TLS
            // index before the string_id store
            { 6, "haloreach.dll",
              "8B 15 ? ? ? ? 8B 00 65 48 8B 0C 25 58 00 00 00 41 B8 B0 05 00 00 48 8B 0C D1 "
              "4A 8B 14 01 8B CB 89 82 6C 01 00 00", 0x2E, ChapterKind::ReachStringId,
              "48 83 EC 28 44 8B D2 E8 ? ? ? ? 84 C0 74 ? 8B 0D ? ? ? ? 65 48 8B 04 25 58 00 00 00 "
              "BA 48 00 00 00",
              0x274DD70, false, PostWin::ClearWonFlag, {}, nullptr, 0, nullptr,
              { kLostPatternH3Reach, 9, 17, 49, nullptr, nullptr,
                KillKind::UnitFlags,
                "48 89 5C 24 08 57 44 8B 15 ? ? ? ? 65 48 8B 04 25 58 00 00 00 BB ? 00 00 00 8B F9 "
                "4A 8B 04 D0 44 0F B7 D1 48 8B 1C 18 4F 8D 1C 52 48 8B 43 50 4E 8B 54 D8 10 "
                "41 8B 82 ? ? 00 00 83 C8 20",
                "8B 08 E8 ? ? ? ? 83 CA FF 3B C2 74 ? 8B 15 ? ? ? ? 65 48 8B 0C 25 58 00 00 00 "
                "41 B8 ? 00 00 00 48 8B 0C D1 4E 8B 04 01 0F B7 C8 48 69 D1 ? ? ? ? 49 8B 40 ? "
                "8B 54 10 ?" } },
        };
        constexpr int kGameCount = sizeof(kGames) / sizeof(kGames[0]);

        typedef void (*TitleFn)(uint16_t index, float duration);
        typedef uint64_t (*Passthrough4Fn)(uint64_t, uint64_t, uint64_t, uint64_t);
        typedef void (*ShellCommandFn)(void* engine, int type, void* context);
        typedef void (*LaunchRequestFn)();

        // How long after a win a launch request is still taken as the win's move to the
        // next mission (H2's ending cinematic can run before it)
        constexpr ULONGLONG kLaunchBlockMs = 120000;

        // How long after a win (or a locked mission starting) MCC's next shell command is
        // replaced with the quit, see GameState::replaceUntil
        constexpr ULONGLONG kReplaceShellMs = 20000;

        // Where the players' unit handles are, parsed from the playerPattern match
        struct PlayerLookup {
            bool ok = false;
            // H3, Reach: the players array is at [[TLS block][slot]]
            const uint32_t* tlsIndex = nullptr;
            uint32_t slot = 0;
            // H2: the players array is at [global]; its next-datum iterator
            uint8_t** global = nullptr;
            int32_t (*next)(void* array, int32_t index) = nullptr;
            // Reach: index of the n-th player; H4: the n-th player's unit
            int32_t (*indexOf)(int32_t n) = nullptr;
            uint32_t (*unitOf)(int32_t n) = nullptr;
            // H3: header fields; the datum size, and the unit handle in the datum
            uint8_t countAt = 0, sizeAt = 0, dataAt = 0;
            uint32_t size = 0;
            uint8_t unitAt = 0;
        };

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
            // Until this tick count, MCC's next shell command other than its status ping
            // (0x5) is replaced with the quit too: a quit sent at the win can land before
            // MCC moves on to the next mission, which then overrides it
            std::atomic<ULONGLONG> replaceUntil{ 0 };
            // The engine's level load (vtable slot 9, as in CE): H3 moves on to the next
            // mission after a win without a shell command, so a load in that window is
            // blocked too
            void* levelLoadTarget = nullptr;
            void* levelLoadOriginal = nullptr;

            // H3: after a win the campaign-advance step is made to fail once, so the game
            // ends instead of starting the next mission (DetourAdvance)
            void* advanceTarget = nullptr;
            void* advanceOriginal = nullptr;
            std::atomic<ULONGLONG> blockAdvanceUntil{ 0 };

            // Reach debug commands. Its chapter and win script functions have no separate
            // implementation to call: the evaluators do the work inline, so /title and /win
            // do what they do (parsed from the win evaluator, see ParseReachWin)
            bool (*reachIsCampaign)() = nullptr;    // the win evaluator's first check
            void (*reachEndGame)() = nullptr;       // ends the game once won
            uint32_t reachFinishedFlag = 0;         // byte in the globals: the game has ended
            std::atomic<ULONGLONG> reachTitleClearAt{ 0 };

            // ClearWonFlag: the won byte is at [[TLS block][wonSlot]] + wonFlag
            const uint32_t* wonTlsIndex = nullptr;
            uint32_t wonSlot = 0;
            uint32_t wonFlag = 0;

            // H2: after a win the next map's launch request is dropped until this tick
            // count, so the next mission never starts loading before the quit lands
            void* launchTarget = nullptr;
            void* launchOriginal = nullptr;
            std::atomic<ULONGLONG> blockLaunchUntil{ 0 };

            // Death Link. The lost byte is at [[TLS block][lostSlot]] + lostFlag.
            void* lostTarget = nullptr;
            void* lostOriginal = nullptr;
            void* tickTarget = nullptr;
            void* tickOriginal = nullptr;
            const uint32_t* lostTlsIndex = nullptr;
            uint32_t lostSlot = 0;
            uint32_t lostFlag = 0;
            void* killFn = nullptr;
            PlayerLookup player;
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

        bool InModule(HMODULE module, const void* p);

        // Sends the pause menu's quit to the engine now. False if the engine or its shell
        // command function isn't known yet.
        bool SendQuit(int gi)
        {
            GameState& st = g_state[gi];
            if (!st.engineGlobal) return false;
            __try
            {
                void* engine = *st.engineGlobal;
                if (!engine) return false;
                // Through the hook's trampoline once it's in, else straight to slot 3
                auto shell = (ShellCommandFn)st.shellOriginal;
                if (!shell)
                {
                    shell = (ShellCommandFn)(*(void***)engine)[3];
                    if (!InModule(st.module, (void*)shell)) return false;
                }
                shell(engine, 0x0, nullptr);  // pause
                shell(engine, 0xD, nullptr);  // teardown
                shell(engine, 0x1, nullptr);  // resume
            }
            __except (1) { return false; }
            printf("[game] %s: quit to the menu sent\n", kGames[gi].dll);
            return true;
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
            {
                if (g_state[GI].launchTarget)
                    g_state[GI].blockLaunchUntil.store(GetTickCount64() + kLaunchBlockMs);
                if (g_state[GI].advanceTarget)
                    g_state[GI].blockAdvanceUntil.store(GetTickCount64() + kLaunchBlockMs);
                g_state[GI].replaceUntil.store(GetTickCount64() + kReplaceShellMs);
                if (!SendQuit(GI))
                    g_state[GI].quitPending.store(true);  // sent on the next tick or shell command
            }
            return result;
        }

        template <int GI>
        void DetourShell(void* engine, int type, void* context)
        {
            auto original = (ShellCommandFn)g_state[GI].shellOriginal;
            if (!original) return;
            GameState& st = g_state[GI];
            if (type != 0x5)
                printf("[game] %s: shell command 0x%x\n", kGames[GI].dll, type);
            ULONGLONG until = st.replaceUntil.load();
            bool replace = st.quitPending.exchange(false);
            if (!replace && type != 0x5 && until && GetTickCount64() < until &&
                st.replaceUntil.compare_exchange_strong(until, 0))
                replace = true;
            if (replace)
            {
                printf("[game] %s: shell command 0x%x replaced with quit to menu\n", kGames[GI].dll, type);
                original(engine, 0x0, nullptr);  // pause
                original(engine, 0xD, nullptr);  // teardown
                original(engine, 0x1, nullptr);  // resume
                return;
            }
            original(engine, type, context);
        }

        typedef void (*LevelLoadFn)(void* engine, const char* path);

        template <int GI>
        void DetourLevelLoad(void* engine, const char* path)
        {
            GameState& st = g_state[GI];
            printf("[game] %s: level load '%s'\n", kGames[GI].dll, path ? path : "(null)");
            ULONGLONG until = st.replaceUntil.load();
            if (until && GetTickCount64() < until && st.replaceUntil.compare_exchange_strong(until, 0))
            {
                printf("[game] %s: level load after the win blocked\n", kGames[GI].dll);
                if (!SendQuit(GI))
                    st.quitPending.store(true);
                return;
            }
            auto original = (LevelLoadFn)st.levelLoadOriginal;
            if (original) original(engine, path);
        }

        void* LevelLoadDetourFor(int gi)
        {
            switch (gi)
            {
            case 0: return (void*)&DetourLevelLoad<0>;
            case 1: return (void*)&DetourLevelLoad<1>;
            case 2: return (void*)&DetourLevelLoad<2>;
            case 3: return (void*)&DetourLevelLoad<3>;
            }
            return nullptr;
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
        // Shows a Reach chapter card the way chud_show_screen_chapter_title does (game thread)
        bool WriteReachChapterSlot(int gi, uint32_t sid)
        {
            const uint32_t* tlsIndex = g_state[gi].reachTlsIndex;
            if (!tlsIndex) return false;
            __try
            {
                uint8_t** tlsArray = (uint8_t**)__readgsqword(0x58);
                uint8_t* block = tlsArray[*tlsIndex];
                uint8_t* slot = *(uint8_t**)(block + 0x5B0);
                *(uint32_t*)(slot + 0x16C) = sid;
                return true;
            }
            __except (1) { return false; }
        }

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

        // H2's main loop request to launch the pending map. Takes no arguments; the
        // original sets the pending flag and starts the loading screen.
        template <int GI>
        void DetourLaunch()
        {
            GameState& st = g_state[GI];
            ULONGLONG until = st.blockLaunchUntil.exchange(0);
            if (until && GetTickCount64() < until)
            {
                printf("[game] %s: next mission launch after the win blocked\n", kGames[GI].dll);
                if (!SendQuit(GI))
                    st.quitPending.store(true);
                return;
            }
            auto original = (LaunchRequestFn)st.launchOriginal;
            if (original) original();
        }

        // H3's campaign advance; takes no arguments, returns whether it started the next map
        template <int GI>
        uint64_t DetourAdvance(uint64_t a, uint64_t b, uint64_t c, uint64_t d)
        {
            GameState& st = g_state[GI];
            ULONGLONG until = st.blockAdvanceUntil.exchange(0);
            if (until && GetTickCount64() < until)
            {
                printf("[game] %s: next mission after the win blocked; the game ends instead\n", kGames[GI].dll);
                return 0;
            }
            auto original = (Passthrough4Fn)st.advanceOriginal;
            return original ? original(a, b, c, d) : 0;
        }

        void* AdvanceDetourFor(int gi)
        {
            switch (gi)
            {
            case 0: return (void*)&DetourAdvance<0>;
            case 1: return (void*)&DetourAdvance<1>;
            case 2: return (void*)&DetourAdvance<2>;
            case 3: return (void*)&DetourAdvance<3>;
            }
            return nullptr;
        }

        void* LaunchDetourFor(int gi)
        {
            switch (gi)
            {
            case 0: return (void*)&DetourLaunch<0>;
            case 1: return (void*)&DetourLaunch<1>;
            case 2: return (void*)&DetourLaunch<2>;
            case 3: return (void*)&DetourLaunch<3>;
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

        // ---- Death Link ----

        constexpr uint32_t kNone = 0xFFFFFFFF;

        // The lost byte (H3, H4, Reach); runs on the game thread
        bool ReadLostFlag(int gi)
        {
            const GameState& st = g_state[gi];
            if (!st.lostTlsIndex) return false;
            __try
            {
                uint8_t** tlsArray = (uint8_t**)__readgsqword(0x58);
                uint8_t* globals = *(uint8_t**)(tlsArray[*st.lostTlsIndex] + st.lostSlot);
                return globals && globals[st.lostFlag] != 0;
            }
            __except (1) { return false; }
        }

        constexpr int kMaxPlayers = 4;

        // Every player's unit handle (kNone for a dead player); returns how many players
        // there are. Runs on the game thread.
        int PlayerUnits(int gi, uint32_t units[kMaxPlayers])
        {
            const PlayerLookup& p = g_state[gi].player;
            if (!p.ok) return 0;
            int n = 0;
            __try
            {
                if (p.global)  // H2
                {
                    uint8_t* players = *p.global;
                    if (!players) return 0;
                    int64_t dataOffset = *(int64_t*)(players + 0x48);
                    if (!dataOffset) return 0;
                    for (int32_t index = p.next(players, -1); index != -1 && n < kMaxPlayers;
                         index = p.next(players, index))
                        units[n++] = *(uint32_t*)(players + dataOffset + (index & 0xFFFF) * p.size + p.unitAt);
                    return n;
                }

                if (p.unitOf)  // H4: like player_get n; NONE for a missing or a dead player
                {
                    for (; n < kMaxPlayers; n++)
                        units[n] = p.unitOf(n);
                    return n;
                }

                uint8_t** tlsArray = (uint8_t**)__readgsqword(0x58);
                uint8_t* players = *(uint8_t**)(tlsArray[*p.tlsIndex] + p.slot);
                if (!players) return 0;
                if (p.indexOf)  // Reach: the n-th player, like player_get n
                {
                    uint8_t* data = *(uint8_t**)(players + p.dataAt);
                    for (int32_t index; n < kMaxPlayers && (index = p.indexOf(n)) != -1;)
                        units[n++] = *(uint32_t*)(data + (index & 0xFFFF) * p.size + p.unitAt);
                    return n;
                }

                // H3: the datums in use, like player_get
                int32_t count = *(int32_t*)(players + p.countAt);
                int32_t size = *(int32_t*)(players + p.sizeAt);
                uint8_t* data = *(uint8_t**)(players + p.dataAt);
                for (int i = 0; i < count && i < kMaxPlayers; i++)
                {
                    uint8_t* datum = data + i * size;
                    if (*(uint16_t*)datum != 0)
                        units[n++] = *(uint32_t*)(datum + p.unitAt);
                }
            }
            __except (1) {}
            return n;
        }

        // Kills every player (in co-op a link is a full loss, as only that sends one) the
        // way the game's unit_kill script does; runs on the game thread
        bool KillPlayers(int gi)
        {
            const GameState& st = g_state[gi];
            const char* dll = kGames[gi].dll;
            if (!st.killFn)
            {
                printf("[deathlink] %s: no way to kill the player, dropped\n", dll);
                return false;
            }
            uint32_t units[kMaxPlayers];
            int count = PlayerUnits(gi, units);
            int killed = 0;
            for (int i = 0; i < count; i++)
            {
                if (units[i] == kNone) continue;
                __try
                {
                    if (kGames[gi].death.kill == KillKind::UnitFlags)
                        ((void (*)(uint32_t, bool, bool, uint32_t, uint8_t))st.killFn)(units[i], false, true, 2, 0);
                    else
                        ((void (*)(uint32_t))st.killFn)(units[i]);
                    killed++;
                }
                __except (1) { printf("[deathlink] %s: kill faulted\n", dll); }
            }
            if (!killed)
                printf("[deathlink] %s: no living player, dropped\n", dll);
            return killed > 0;
        }

        // Takes a pending link and applies it, unless the player is already dead
        void ApplyDeathLink(int gi, bool alreadyDead)
        {
            if (!TakeDeathLinkKill()) return;
            if (alreadyDead)
                printf("[deathlink] %s: player already dead, dropped\n", kGames[gi].dll);
            else if (KillPlayers(gi))
                NoteDeathLinkKill(kGames[gi].code);
        }

        // Runs a pending debug command through the hooked functions (game thread)
        // Reach's win evaluator, after its campaign check: is the game over already; if
        // not, set the won byte and end the game. False if it couldn't (not a campaign,
        // already over, faulted).
        bool ReachWin(int gi)
        {
            GameState& st = g_state[gi];
            __try
            {
                if (!st.reachIsCampaign()) return false;
                uint8_t** tlsArray = (uint8_t**)__readgsqword(0x58);
                uint8_t* block = tlsArray[*st.wonTlsIndex];
                uint8_t* globals = *(uint8_t**)(block + st.wonSlot);
                if (globals[st.reachFinishedFlag]) return false;
                globals[st.wonFlag] = 1;
                st.reachEndGame();
                return true;
            }
            __except (1) { return false; }
        }

        // "call rel32" at p: its target
        void* CallTarget(uint8_t* p)
        {
            return p + 5 + *(int32_t*)(p + 1);
        }

        // Reach's game_won evaluator: "call is_campaign", ..., "cmp byte [rcx + finished], 0",
        // "jne", "mov byte [rcx + won], 1", "call end_game"
        bool ParseReachWin(uint8_t* fn, GameState& st)
        {
            __try
            {
                for (int i = 0; i < 0x20 && !st.reachIsCampaign; i++)
                    if (fn[i] == 0xE8)
                        st.reachIsCampaign = (bool (*)())CallTarget(fn + i);
                for (int i = 0; i < 0x50 && !st.reachFinishedFlag; i++)
                    if (fn[i] == 0x80 && fn[i + 1] == 0xB9 && fn[i + 6] == 0x00)
                        st.reachFinishedFlag = *(uint32_t*)(fn + i + 2);
                for (int i = 0; i < 0x50 && !st.reachEndGame; i++)
                    if (fn[i] == 0xC6 && fn[i + 1] == 0x81 && fn[i + 6] == 0x01 && fn[i + 7] == 0xE8)
                        st.reachEndGame = (void (*)())CallTarget(fn + i + 7);
            }
            __except (1) { return false; }
            return st.reachIsCampaign && st.reachFinishedFlag && st.reachEndGame &&
                   InModule(st.module, (void*)st.reachIsCampaign) && InModule(st.module, (void*)st.reachEndGame);
        }

        void RunDebugAction(int gi)
        {
            GameState& st = g_state[gi];
            const char* dll = kGames[gi].dll;

            // A card /title put up comes down again, as the scripts' clear call does
            ULONGLONG clearAt = st.reachTitleClearAt.load();
            if (clearAt && GetTickCount64() >= clearAt && st.reachTitleClearAt.compare_exchange_strong(clearAt, 0))
                WriteReachChapterSlot(gi, 0);

            int arg = 0;
            DebugAction action = TakeDebugAction(arg);
            if (action == DebugAction::None) return;
            if (action == DebugAction::Title && kGames[gi].chapterKind == ChapterKind::ReachStringId)
            {
                // arg: the chapter's runtime string_id (tools/reach_chapter_sids.json)
                if (!WriteReachChapterSlot(gi, (uint32_t)arg))
                    DebugReport("%s: chapter slot not found", dll);
                else
                {
                    ReportChapter(gi, (uint32_t)arg);
                    st.reachTitleClearAt.store(GetTickCount64() + 5000);
                    DebugReport("%s: title %d shown", dll, arg);
                }
            }
            else if (action == DebugAction::Win && kGames[gi].chapterKind == ChapterKind::ReachStringId)
            {
                if (!st.reachEndGame || !st.wonTlsIndex)
                    DebugReport("%s: win evaluator not parsed", dll);
                else
                {
                    ReportWon(gi);
                    if (ReachWin(gi))
                    {
                        ClearWonFlag(gi);
                        DebugReport("%s: won", dll);
                    }
                    else
                        DebugReport("%s: not won (no campaign running, or it's over)", dll);
                }
            }
            else if (action == DebugAction::Title)
            {
                if (!st.chapterTarget)
                    DebugReport("%s: chapter hook not installed", dll);
                else
                    ((TitleFn)st.chapterTarget)((uint16_t)arg, 3.0f);
            }
            else if (action == DebugAction::Win)
            {
                if (!st.wonTarget)
                    DebugReport("%s: mission-won hook not installed", dll);
                else
                    ((Passthrough4Fn)st.wonTarget)(0, 0, 0, 0);
            }
        }

        // H3, H4, Reach: game_lost(bool all_players_dead)
        template <int GI>
        uint64_t DetourLost(uint64_t a, uint64_t b, uint64_t c, uint64_t d)
        {
            RunDebugAction(GI);
            bool before = ReadLostFlag(GI);
            ApplyDeathLink(GI, before || (uint8_t)a != 0);
            auto original = (Passthrough4Fn)g_state[GI].lostOriginal;
            uint64_t result = original ? original(a, b, c, d) : 0;
            if (!before && ReadLostFlag(GI))
                ReportDeath(g_pipe, kGames[GI].code);
            return result;
        }

        // H2: runs once the lost byte is set
        template <int GI>
        uint64_t DetourLostEdge(uint64_t a, uint64_t b, uint64_t c, uint64_t d)
        {
            ReportDeath(g_pipe, kGames[GI].code);
            auto original = (Passthrough4Fn)g_state[GI].lostOriginal;
            return original ? original(a, b, c, d) : 0;
        }

        // H2: players-all-dead getter, the tick a link is applied from
        template <int GI>
        uint64_t DetourTick(uint64_t a, uint64_t b, uint64_t c, uint64_t d)
        {
            RunDebugAction(GI);
            auto original = (Passthrough4Fn)g_state[GI].tickOriginal;
            uint64_t result = original ? original(a, b, c, d) : 0;
            ApplyDeathLink(GI, (uint8_t)result != 0);
            return result;
        }

        void* const kLostDetours[] = { (void*)&DetourLost<0>, (void*)&DetourLost<1>,
                                       (void*)&DetourLost<2>, (void*)&DetourLost<3> };
        void* const kLostEdgeDetours[] = { (void*)&DetourLostEdge<0>, (void*)&DetourLostEdge<1>,
                                           (void*)&DetourLostEdge<2>, (void*)&DetourLostEdge<3> };
        void* const kTickDetours[] = { (void*)&DetourTick<0>, (void*)&DetourTick<1>,
                                       (void*)&DetourTick<2>, (void*)&DetourTick<3> };

        // The address a rip-relative disp32 at match + at points to
        template <typename T>
        T* RipTarget(uint8_t* match, int at)
        {
            return (T*)(match + at + 4 + *(int32_t*)(match + at));
        }

        bool Hook(const char* what, const char* dll, void* target, void* detour, void** original);

        void InstallDeathLink(int gi, HMODULE module)
        {
            const GameDef& def = kGames[gi];
            const DeathDef& dd = def.death;
            GameState& st = g_state[gi];

            if (dd.lostPattern)
            {
                uint8_t* lost = (uint8_t*)FindPatternInModule(module, dd.lostPattern);
                if (!lost)
                    printf("[game] %s: game_lost pattern not found; deaths won't be sent\n", def.dll);
                else if (Hook("game_lost", def.dll, lost, kLostDetours[gi], &st.lostOriginal))
                {
                    st.lostTarget = lost;
                    st.lostTlsIndex = RipTarget<const uint32_t>(lost, dd.lostTlsAt);
                    st.lostSlot = *(uint32_t*)(lost + dd.lostSlotAt);
                    st.lostFlag = *(uint32_t*)(lost + dd.lostFlagAt);
                }
            }
            if (dd.lostEdgePattern)
            {
                void* edge = FindPatternInModule(module, dd.lostEdgePattern);
                if (!edge)
                    printf("[game] %s: game-lost pattern not found; deaths won't be sent\n", def.dll);
                else if (Hook("game-lost", def.dll, edge, kLostEdgeDetours[gi], &st.lostOriginal))
                    st.lostTarget = edge;
            }
            if (dd.tickPattern)
            {
                void* tick = FindPatternInModule(module, dd.tickPattern);
                if (!tick)
                    printf("[game] %s: all-dead pattern not found; links can't kill\n", def.dll);
                else if (Hook("all-dead", def.dll, tick, kTickDetours[gi], &st.tickOriginal))
                    st.tickTarget = tick;
            }

            if (dd.killPattern)
                st.killFn = FindPatternInModule(module, dd.killPattern);
            uint8_t* p = dd.playerPattern ? (uint8_t*)FindPatternInModule(module, dd.playerPattern) : nullptr;
            PlayerLookup& pl = st.player;
            if (p && def.code == 2)
            {
                pl.global = RipTarget<uint8_t*>(p, 18);
                pl.next = (int32_t (*)(void*, int32_t))RipTarget<uint8_t>(p, 30);
                pl.size = *(uint32_t*)(p + 79);
                pl.unitAt = p[87];
                pl.ok = true;
            }
            else if (p && def.code == 4)
            {
                pl.unitOf = (uint32_t (*)(int32_t))p;
                pl.ok = true;
            }
            else if (p && dd.kill == KillKind::UnitFlags)  // Reach
            {
                pl.indexOf = (int32_t (*)(int32_t))RipTarget<uint8_t>(p, 3);
                pl.tlsIndex = RipTarget<const uint32_t>(p, 16);
                pl.slot = *(uint32_t*)(p + 31);
                pl.size = *(uint32_t*)(p + 49);
                pl.dataAt = p[56];
                pl.unitAt = p[60];
                pl.ok = true;
            }
            else if (p)  // H3
            {
                pl.tlsIndex = RipTarget<const uint32_t>(p, 20);
                pl.slot = *(uint32_t*)(p + 26);
                pl.countAt = p[46];
                pl.sizeAt = p[52];
                pl.dataAt = p[63];
                pl.unitAt = p[91];
                pl.ok = true;
            }
            if (dd.kill != KillKind::None && (!st.killFn || !pl.ok))
                printf("[game] %s: %s not found; links can't kill\n", def.dll,
                       st.killFn ? "player lookup" : "unit_kill");
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
            DropHook(st.levelLoadTarget, st.levelLoadOriginal, sameModule);
            DropHook(st.launchTarget, st.launchOriginal, sameModule);
            DropHook(st.advanceTarget, st.advanceOriginal, sameModule);
            st.blockAdvanceUntil.store(0);
            DropHook(st.lostTarget, st.lostOriginal, sameModule);
            DropHook(st.tickTarget, st.tickOriginal, sameModule);
            st.lostTlsIndex = nullptr;
            st.lostSlot = st.lostFlag = 0;
            st.killFn = nullptr;
            st.player = PlayerLookup{};
            st.blockLaunchUntil.store(0);
            st.hookedModule = module;
            st.engineGlobal = nullptr;
            st.quitPending.store(false);
            st.replaceUntil.store(0);
            st.wonTlsIndex = nullptr;
            st.wonSlot = st.wonFlag = 0;
            st.reachTlsIndex = nullptr;
            st.reachIsCampaign = nullptr;
            st.reachEndGame = nullptr;
            st.reachFinishedFlag = 0;
            st.reachTitleClearAt.store(0);
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
                else if (def.chapterKind == ChapterKind::ReachStringId && !ParseReachWin((uint8_t*)wonTarget, st))
                    printf("[game] %s: win evaluator not parsed; /win won't work\n", def.dll);
            }
            else
            {
                st.engineGlobal = FindEngineGlobal(module);
                if (!st.engineGlobal)
                    printf("[game] %s: engine global not found; a win will load the next mission\n", def.dll);
            }

            if (def.launchPattern)
            {
                void* launch = FindPatternInModule(module, def.launchPattern);
                if (!launch)
                    printf("[game] %s: launch request pattern not found; a win may load the next mission\n", def.dll);
                else if (Hook("launch request", def.dll, launch, LaunchDetourFor(gi), &st.launchOriginal))
                    st.launchTarget = launch;
            }

            if (def.advancePattern)
            {
                void* advance = FindPatternInModule(module, def.advancePattern);
                if (!advance)
                    printf("[game] %s: campaign advance pattern not found; a win may load the next mission\n", def.dll);
                else if (Hook("campaign advance", def.dll, advance, AdvanceDetourFor(gi), &st.advanceOriginal))
                    st.advanceTarget = advance;
            }

            InstallDeathLink(gi, module);

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
            void* levelLoad = nullptr;
            __try
            {
                void* engine = *st.engineGlobal;
                if (!engine) return;
                target = (*(void***)engine)[3];
                levelLoad = (*(void***)engine)[9];
            }
            __except (1) { return; }
            if (!InModule(st.module, target)) return;
            if (Hook("shell command", kGames[gi].dll, target, ShellDetourFor(gi), &st.shellOriginal))
                st.shellTarget = target;
            else
                st.engineGlobal = nullptr;  // don't retry every tick
            if (st.shellTarget && levelLoad != target && InModule(st.module, levelLoad) &&
                Hook("level load", kGames[gi].dll, levelLoad, LevelLoadDetourFor(gi), &st.levelLoadOriginal))
                st.levelLoadTarget = levelLoad;
        }
    }

    namespace {
        // MinHook puts a "jmp rel32" (E9) at each hooked target. MCC can unload a game DLL
        // and load it again at the same base between two ticks (H3 does when quitting to
        // the menu), which leaves the same HMODULE but the game's own code, unhooked.
        bool HooksWereReset(const GameState& st)
        {
            const void* targets[] = { st.chapterTarget, st.wonTarget, st.skullTarget[0],
                                      st.skullTarget[1], st.shellTarget, st.launchTarget,
                                      st.levelLoadTarget, st.advanceTarget,
                                      st.lostTarget, st.tickTarget };
            for (const void* target : targets)
            {
                if (!target) continue;
                __try { if (*(const uint8_t*)target != 0xE9) return true; }
                __except (1) { return true; }
            }
            return false;
        }
    }

    bool DebugLoadLevel(const std::string& path)
    {
        // In a mission only the running game's DLL is loaded
        static const char* const kDlls[] = { "halo1.dll", "halo2.dll", "halo3.dll", "halo4.dll", "haloreach.dll" };
        HMODULE module = nullptr;
        int loaded = 0;
        for (const char* dll : kDlls)
            if (HMODULE m = GetModuleHandleA(dll)) { module = m; loaded++; }
        if (loaded != 1)
        {
            DebugReport("load: not in a mission");
            return false;
        }
        void** global = FindEngineGlobal(module);
        // The engine copies the path (CE strdups it); keep ours alive anyway
        static std::string s_path;
        s_path = path;
        __try
        {
            void* engine = global ? *global : nullptr;
            void* load = engine ? (*(void***)engine)[9] : nullptr;
            if (!load || !InModule(module, load))
            {
                DebugReport("load: engine not found");
                return false;
            }
            // Around the post-win block (DetourLevelLoad), which this isn't
            for (int gi = 0; gi < kGameCount; gi++)
                if (g_state[gi].module == module && g_state[gi].levelLoadOriginal)
                {
                    g_state[gi].replaceUntil.store(0);
                    load = g_state[gi].levelLoadOriginal;
                }
            ((void (*)(void*, const char*))load)(engine, s_path.c_str());
        }
        __except (1)
        {
            DebugReport("load: faulted");
            return false;
        }
        DebugReport("load: %s requested", path.c_str());
        return true;
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
            else if (module && HooksWereReset(st))
            {
                printf("[game] %s reloaded at the same address, reinstalling hooks\n", kGames[gi].dll);
                InstallGame(gi, module);
            }
        }

        for (int gi = 0; gi < kGameCount; gi++)
            if (g_state[gi].module && kGames[gi].postWin == PostWin::ShellQuit)
            {
                TryHookShell(gi);
                if (g_state[gi].quitPending.load() && SendQuit(gi))
                    g_state[gi].quitPending.store(false);
            }

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
                    st.replaceUntil.store(GetTickCount64() + kReplaceShellMs);
                    if (!SendQuit(gi))
                        st.quitPending.store(true);
                }
        }
    }

}  // namespace haloap
