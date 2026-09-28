#pragma once

#include <set>
#include <mutex>
#include <cstdint>

namespace haloap {

    // Game codes match the apworld's (skulls.GAME_INFO) and the lobby detection:
    // 1 CE, 2 H2, 3 H3, 4 H4, 5 ODST, 6 Reach.
    constexpr int kItemGameCount = 7;
    constexpr int kMaxMissions = 32;

    class ItemHandler {
    public:
        // Call when an item is received from the AP server.
        // Handles mission unlock items and skull items.
        void addItem(int itemID);

        // Whether mission `missionId` (0-based, the game's menu/play order) of `game`
        // may be picked. A game the seed never mentioned isn't restricted.
        bool isMissionAllowed(int game, int missionId) const;

        // CE (game 1): what the pre-1.3 single-game callers mean
        bool isMissionAllowed(int missionId) const { return isMissionAllowed(1, missionId); }

        // Get the number of currently unlocked missions across all games.
        int getUnlockedCount() const;

        // Mission indices of `game` whose completion location is checked
        void setMissionCompletions(int game, const bool completed[kMaxMissions]);

        void setFinalMission(int game, int idx);

        // How many of the game's other missions must be completed before its final one opens
        void setMissionsRequired(int game, int count);

    private:
        struct GameState {
            bool managed = false;  // the seed includes this game
            std::set<int> unlocked;
            bool completed[kMaxMissions] = {};
            int finalMission = -1;
            int missionsRequired = kMaxMissions;  // until told, the final stays locked
        };

        mutable std::mutex m_mutex;
        GameState m_games[kItemGameCount];

        // Mission unlock item -> (game, mission index); false if not a mission item.
        // IDs are game * 100000 + (index + 1) * 1000.
        static bool translateItemToMission(int itemID, int& game, int& missionId);
    };

    // Global singleton instance.
    ItemHandler& GetItemHandler();

}  // namespace haloap