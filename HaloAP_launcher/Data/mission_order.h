#pragma once

// Generated from apworld/halo_mcc/data/missions.py (plus CE): each game's missions in
// play order, which is also the order of its MCC mission list. Index i here is menu
// index i and AP mission ID code * 100000 + (i + 1) * 1000.

#include <string>
#include <vector>

namespace haloap {

    struct GameMissionOrder {
        const char* key;   // apworld game key, as used in slot data
        int code;          // apworld / DLL game code
        std::vector<std::string> missions;
    };

    inline const std::vector<GameMissionOrder>& GetGameMissionOrders() {
        static const std::vector<GameMissionOrder> orders = {
            {"ce", 1, {
                "The Pillar of Autumn",
                "Halo (CE)",
                "The Truth and Reconciliation",
                "The Silent Cartographer",
                "Assault on the Control Room",
                "343 Guilty Spark",
                "The Library",
                "Two Betrayals",
                "Keyes",
                "The Maw",
            }},
            {"h2a", 2, {
                "The Heretic",
                "The Armory",
                "Cairo Station",
                "Outskirts",
                "Metropolis",
                "The Arbiter",
                "The Oracle",
                "Delta Halo",
                "Regret",
                "Sacred Icon",
                "Quarantine Zone",
                "Gravemind",
                "Uprising",
                "High Charity",
                "The Great Journey",
            }},
            {"h3", 3, {
                "Arrival",
                "Sierra 117",
                "Crow's Nest",
                "Tsavo Highway",
                "The Storm",
                "Floodgate",
                "The Ark",
                "The Covenant",
                "Cortana",
                "Halo",
                "Epilogue",
            }},
            {"h4", 4, {
                "Prologue",
                "Dawn",
                "Requiem",
                "Forerunner",
                "Infinity",
                "Reclaimer",
                "Shutdown",
                "Composer",
                "Midnight",
                "Epilogue",
            }},
            {"reach", 6, {
                "Noble Actual",
                "Winter Contingency",
                "ONI: Sword Base",
                "Nightfall",
                "Tip of the Spear",
                "Long Night of Solace",
                "Exodus",
                "New Alexandria",
                "The Package",
                "The Pillar of Autumn",
                "Lone Wolf",
            }},
        };
        return orders;
    }

}  // namespace haloap
