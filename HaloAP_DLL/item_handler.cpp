#include "item_handler.h"
#include "hooks/skull_hook.h"
#include <cstdio>

namespace haloap {

    void ItemHandler::addItem(int itemID) {
        int game, missionId;
        if (translateItemToMission(itemID, game, missionId)) {
            std::lock_guard<std::mutex> lock(m_mutex);
            GameState& g = m_games[game];
            g.managed = true;
            if (g.unlocked.insert(missionId).second)
                printf("[items] Game %d mission %d unlocked (AP item %d)\n", game, missionId, itemID);
            return;
        }

        if (haloap::UnlockSkullItem(itemID))
            return;

        printf("[items] Unknown item recieved: %d\n", itemID);
    }

    void ItemHandler::setFinalMission(int game, int idx)
    {
        if (game < 1 || game >= kItemGameCount || idx < 0 || idx >= kMaxMissions) return;
        std::lock_guard<std::mutex> lock(m_mutex);
        m_games[game].managed = true;
        m_games[game].finalMission = idx;
        printf("[items] Game %d final mission set to %d\n", game, idx);
    }

    void ItemHandler::setMissionsRequired(int game, int count)
    {
        if (game < 1 || game >= kItemGameCount || count < 0) return;
        std::lock_guard<std::mutex> lock(m_mutex);
        m_games[game].missionsRequired = count;
    }

    void ItemHandler::setMissionCompletions(int game, const bool completed[kMaxMissions]) {
        if (game < 1 || game >= kItemGameCount) return;
        std::lock_guard<std::mutex> lock(m_mutex);
        for (int i = 0; i < kMaxMissions; i++)
            m_games[game].completed[i] = completed[i];
    }

    bool ItemHandler::isMissionAllowed(int game, int missionId) const {
        if (game < 1 || game >= kItemGameCount || missionId < 0 || missionId >= kMaxMissions)
            return true;

        std::lock_guard<std::mutex> lock(m_mutex);
        const GameState& g = m_games[game];
        if (!g.managed)
            return true;

        // Final mission unlocked when enough of the others are completed
        if (missionId == g.finalMission) {
            int completed = 0;
            for (int i = 0; i < kMaxMissions; i++)
                if (i != g.finalMission && g.completed[i]) completed++;
            return completed >= g.missionsRequired;
        }

        // All other missions: unlocked via AP items
        return g.unlocked.count(missionId) > 0;
    }

    int ItemHandler::getUnlockedCount() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        int n = 0;
        for (const GameState& g : m_games) n += static_cast<int>(g.unlocked.size());
        return n;
    }

    ItemHandler& GetItemHandler() {
        static ItemHandler instance;
        return instance;
    }

    bool ItemHandler::translateItemToMission(int itemID, int& game, int& missionId) {
        game = itemID / 100000;
        int rest = itemID % 100000;
        if (game < 1 || game >= kItemGameCount || rest % 1000 != 0) return false;
        int n = rest / 1000;  // 1-based mission number
        if (n < 1 || n > kMaxMissions) return false;
        missionId = n - 1;
        return true;
    }

}  // namespace haloap
