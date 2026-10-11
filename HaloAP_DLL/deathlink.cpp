#include "deathlink.h"
#include "pipe_client.h"
#include <windows.h>
#include <atomic>
#include <cstdio>

namespace haloap {

    namespace {
        // A received link waits this long for a game thread to apply it
        constexpr ULONGLONG kKillTimeoutMs = 10000;
        // After a kill, the next death within this window is the link's. Death to
        // game-over takes a moment; a kill that didn't take (e.g. the player can't die
        // in a cutscene) just runs out.
        constexpr ULONGLONG kLinkedDeathWindowMs = 10000;

        std::atomic<ULONGLONG> g_killRequestedAt{ 0 };
        std::atomic<ULONGLONG> g_linkedDeathUntil{ 0 };
    }

    void RequestDeathLinkKill(const std::string& source)
    {
        printf("[deathlink] received from %s\n", source.c_str());
        g_killRequestedAt.store(GetTickCount64());
    }

    bool TakeDeathLinkKill()
    {
        ULONGLONG at = g_killRequestedAt.load();
        if (!at || !g_killRequestedAt.compare_exchange_strong(at, 0))
            return false;
        if (GetTickCount64() - at > kKillTimeoutMs)
        {
            printf("[deathlink] not in a mission in time, dropped\n");
            return false;
        }
        return true;
    }

    void NoteDeathLinkKill(int game)
    {
        printf("[deathlink] game %d: player killed\n", game);
        g_linkedDeathUntil.store(GetTickCount64() + kLinkedDeathWindowMs);
    }

    void ReportDeath(PipeClient* pipe, int game)
    {
        ULONGLONG until = g_linkedDeathUntil.exchange(0);
        bool linked = until && GetTickCount64() < until;
        std::string msg = (linked ? "G_DEATH_LINKED:" : "G_DEATH:") + std::to_string(game);
        printf("[deathlink] -> %s\n", msg.c_str());
        if (pipe && pipe->IsConnected())
            pipe->SendAsync(msg);
    }

}  // namespace haloap
