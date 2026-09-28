#pragma once
#include "../pipe_client.h"

namespace haloap {

    // Hook OnSkullClaimed in halo1.dll (RVA 0x63640). Fires when the player
    // walks into a skull trigger zone. Sends "LOCATION_CHECKED: <id>" to the AP
    // server via the pipe for each valid skull pickup.
    bool InstallSkullHook(PipeClient* pipe);
    void UninstallSkullHook();

    // Apply the current forced-skull set to MCC's skull bitmask in game memory,
    // limited to the skulls the lobby's game has. Called each worker tick to keep
    // forced skulls active across level loads.
    void ApplyForcedSkulls();

    // Set which skulls are forced on based on the skullsanity tier from AP slot
    // data. Tiers: 0=off, 1=non_scoring, 2=hard, 3=harder, 4=laso.
    void SetSkullsanityTier(int tier);

    // Unlock the skull a received skull item stands for. Handles per-game and
    // shared items (see the apworld's data/skulls.py) and the 1.2.1 CE item IDs.
    // Returns false if itemID isn't a skull item.
    bool UnlockSkullItem(int itemID);

    // Set which game's lobby is open, by apworld game code (1 CE, 2 Halo 2,
    // 3 Halo 3, 4 Halo 4, 5 ODST, 6 Reach). Forced and unlocked skulls follow it.
    void SetLobbyGame(int game);

    // Track whether the player is currently inside a mission. ApplyForcedSkulls
    // only runs when NOT in a mission (bitmask pointer chain is lobby-only).
    void SetInMission(bool inMission);
    
    // Unlocked / skullsanity-managed skull bits for the lobby's game
    uint64_t GetUnlockedMask();
    
    uint64_t GetForcedMask();

}  // namespace haloap