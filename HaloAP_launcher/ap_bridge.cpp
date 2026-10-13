#include "ap_bridge.h"
#include "Data/mission_map.h"
#include "Data/chapter_map.h"
#include "Data/mission_order.h"
#include "shared/common.h"
#include <algorithm>
#include <iostream>
#include <vector>
#include <set>
#include <sstream>
#include <string>


namespace haloap {
    
    static const int64_t COMPLETION_LOCATIONS[] = {
        101000, 102000, 103000, 104000, 105000,
        106000, 107000, 108000, 109000, 110000
    };
    
    std::unordered_map<std::string, int> MISSION_NAME_TO_INDEX = {
    {"The Pillar of Autumn", 0},
    {"Halo", 1},
    {"The Truth and Reconciliation", 2},
    {"The Silent Cartographer", 3},
    {"Assault on the Control Room", 4},
    {"343 Guilty Spark", 5},
    {"The Library", 6},
    {"Two Betrayals", 7},
    {"Keyes", 8},
    {"The Maw", 9},
    };  
    int m_finalMission = 9;

    // Level names are "<Game>: <Mission>" (CE's too since 1.4). Returns the bare mission
    // name, also mapping pre-1.4 CE names ("Halo (CE)", no prefix) to the current ones.
    std::string BareMissionName(const std::string& name)
    {
        size_t colon = name.find(": ");
        std::string bare = colon != std::string::npos ? name.substr(colon + 2) : name;
        return bare == "Halo (CE)" ? "Halo" : bare;
    }
    
    std::unordered_map<std::string, int> MISSION_CODE_TO_INDEX = {
    {"a10", 0},
    {"a30", 1},
    {"a50", 2},
    {"b30", 3},
    {"b40", 4},
    {"c10", 5},
    {"c20", 6},
    {"c40", 7},
    {"d20", 8},
    {"d40", 9},
    };
    
    std::string m_mission;
    
    void APBridge::SendCompletionState() {
        if (!m_sendToDll) return;
        std::lock_guard<std::mutex> lock(m_checkedMutex);

        // Pre-1.3 slot data has no per-game finals: CE only, as before
        std::map<int, int> finals = m_finalByGame;
        if (finals.empty())
            finals[1] = m_finalMission;

        for (const auto& [code, finalIdx] : finals) {
            size_t count = 10;
            for (const auto& order : GetGameMissionOrders())
                if (order.code == code) count = order.missions.size();

            std::string msg = "COMPLETED:" + std::to_string(code) + ":";
            bool first = true;
            for (size_t i = 0; i < count; i++) {
                if (m_checkedLocations.count(int64_t(code) * 100000 + int64_t(i + 1) * 1000)) {
                    if (!first) msg += ",";
                    msg += std::to_string(i);
                    first = false;
                }
            }
            m_sendToDll(msg);
            std::cout << "[ap] Sent completion state: " << msg << "\n";

            m_sendToDll("FINAL_MISSION:" + std::to_string(code) + ":" + std::to_string(finalIdx));
            std::cout << "[ap] Sent game " << code << " final mission: " << finalIdx << "\n";

            // Without a count in slot data (pre-1.3), the final needs all the others
            auto req = m_requiredByGame.find(code);
            int required = req != m_requiredByGame.end() ? req->second : int(count) - 1;
            m_sendToDll("MISSIONS_REQUIRED:" + std::to_string(code) + ":" + std::to_string(required));
            std::cout << "[ap] Sent game " << code << " missions required: " << required << "\n";
        }
    }

    // Whether a non-CE mission is playable in this seed, as the DLL's menu decides it: its
    // Access item was received, or it's the final and enough of the others are completed.
    // Games without a final in slot data aren't restricted.
    bool APBridge::IsMissionUnlocked(int code, int index, size_t missionCount) {
        auto final = m_finalByGame.find(code);
        if (final == m_finalByGame.end())
            return true;

        const int64_t accessId = int64_t(code) * 100000 + int64_t(index + 1) * 1000;
        {
            std::lock_guard<std::mutex> lock(m_itemBufferMutex);
            if (std::find(m_itemBuffer.begin(), m_itemBuffer.end(), accessId) != m_itemBuffer.end())
                return true;
        }
        if (index != final->second)
            return false;

        auto req = m_requiredByGame.find(code);
        int required = req != m_requiredByGame.end() ? req->second : int(missionCount) - 1;
        int done = 0;
        std::lock_guard<std::mutex> lock(m_checkedMutex);
        for (size_t i = 0; i < missionCount; i++)
            if (int(i) != index && m_checkedLocations.count(int64_t(code) * 100000 + int64_t(i + 1) * 1000))
                done++;
        return done >= required;
    }

    APBridge::APBridge() = default;

    APBridge::~APBridge() {
        Stop();
    }
    
    void APBridge::ReplayBufferedItems() {
        if (!m_sendToDll) return;
        if (m_skullsanityTier >= 0)
        {
            m_sendToDll("SKULLSANITY: "+ std::to_string(m_skullsanityTier));
        }
        
        std::lock_guard<std::mutex> lock(m_itemBufferMutex);
        std::cout << "[ap] replaying " << m_itemBuffer.size() << " buffered items to DLL\n";
        for (int64_t itemId : m_itemBuffer) {
            m_sendToDll("ITEM_RECIVED: " + std::to_string(itemId));
        }
        // Also send current completion state
        SendCompletionState();
    }

    bool APBridge::Start(const std::string& serverUri,
        const std::string& game,
        const std::string& slot,
        const std::string& password) {
        m_game = game;
        m_slot = slot;
        m_password = password;

        try {
            // Construct APClient. The UUID should be stable across runs for a user
            // so the server recognizes them, but for alpha we generate one per run.
            std::string uuid = "";
            m_client = std::make_unique<APClient>(uuid, game, serverUri);
        }
        catch (const std::exception& e) {
            std::cerr << "[ap] APClient construction failed: " << e.what() << "\n";
            return false;
        }

        // Register callbacks. Captures `this`; lifetime is fine because the client
        // is owned by us and callbacks only fire during Poll().
        m_client->set_socket_connected_handler([this]() { OnSocketConnected(); });
        m_client->set_socket_error_handler([this](const std::string& err) { OnSocketError(err); });
        m_client->set_socket_disconnected_handler([this]() { OnSocketDisconnected(); });
        m_client->set_room_info_handler([this]() { OnRoomInfo(); });
        m_client->set_slot_connected_handler([this](const nlohmann::json& data) { OnSlotConnected(data); });
        m_client->set_slot_refused_handler([this](const std::list<std::string>& reasons) { OnSlotRefused(reasons); });
        m_client->set_retrieved_handler([this](const std::map<std::string, nlohmann::json>& keys) {
            auto amnesty = keys.find(AmnestyKey());
            if (amnesty != keys.end() && amnesty->second.is_number_integer()) {
                std::lock_guard<std::mutex> lock(m_deathMutex);
                m_deathsForgiven = amnesty->second.get<int>();
                std::cout << "[deathlink] " << m_deathsForgiven << "/" << m_deathLinkAmnesty
                          << " deaths forgiven so far\n";
            }
            auto it = keys.find(FinalsKey());
            if (it == keys.end() || !it->second.is_array()) return;
            {
                std::lock_guard<std::mutex> lock(m_checkedMutex);
                for (const auto& v : it->second)
                    if (v.is_number_integer()) m_finalsDone.insert(v.get<int>());
            }
            std::cout << "[ap] " << it->second.dump() << " final missions done in earlier sessions\n";
        });
        m_client->set_items_received_handler([this](const std::list<APClient::NetworkItem>& items) { OnItemsReceived(items); });
        m_client->set_print_json_handler([this](const APClient::PrintJSONArgs& args) { OnPrintJson(args); });
        m_client->set_bounced_handler([this](const nlohmann::json& packet) { OnBounced(packet); });

        std::cout << "[ap] connecting to " << serverUri << " as slot '" << slot << "'...\n";
        return true;
    }

    void APBridge::Poll() {
        if (m_stopped.load()) return;
        if (m_client) {
            m_client->poll();
        }

        std::vector<std::string> messages;
        {
            std::lock_guard<std::mutex> lock(m_dllQueueMutex);
            messages.swap(m_dllQueue);
        }
        for (const auto& message : messages)
            HandleDllMessage(message);
    }

    void APBridge::QueueDllMessage(const std::string& message) {
        std::lock_guard<std::mutex> lock(m_dllQueueMutex);
        m_dllQueue.push_back(message);
    }

    void APBridge::Stop() {
        if (m_stopped.exchange(true)) return;
        m_client.reset();
        m_socketConnected.store(false);
        m_slotConnected.store(false);
    }

    bool APBridge::HandleDllMessage(const std::string& message) {
        const std::string missionCompPrefix = "MISSION_COMPLETE: ";
        if (message.rfind(missionCompPrefix, 0) == 0) {
            std::string missionCode = message.substr(missionCompPrefix.size());
            const auto& map = GetMissionIdMap();
            auto it = map.find(missionCode);
            if (it == map.end()) {
                std::cerr << "[ap] unknown mission code: " << missionCode << "\n";
                return true;  // we recognized the message type, just couldn't map it
            }

            int64_t locationId = it->second;
            std::cout << "[ap] MISSION_COMPLETE: " << missionCode
                << " -> location " << locationId
                << " (" << GetMissionDisplayName(locationId) << ")\n";

            SendLocation(locationId);
            SendMissionChapters(1, MISSION_CODE_TO_INDEX[missionCode]);
        
            if (MISSION_CODE_TO_INDEX[missionCode] == m_finalMission)
                OnFinalMissionComplete(1);
        
            return true;
        }
        const std::string missionPrefix = "MISSION_LOAD: ";
        if (message.rfind(missionPrefix, 0) == 0)
        {
            std::string missionCode = message.substr(missionPrefix.size());
            // Extract mission code from "path='levels\d40\d40'"
            size_t levelsPos = missionCode.find("levels\\");
            if (levelsPos != std::string::npos) {
                size_t start = levelsPos + 7; // length of "levels\"
                size_t end = missionCode.find('\\', start);
                if (end != std::string::npos) {
                    m_mission = missionCode.substr(start, end - start);
                }
            }
            std::cout << "[launcher] Map: " << m_mission << "\n";
            return true;
        }
        const std::string chapterPrefix = "CHAPTER:";
        if (message.rfind(chapterPrefix, 0) == 0)
        {
            // "CHAPTER:<map>:<index>"; DLLs before 1.4 send "CHAPTER:<index>" and the map
            // comes from the last MISSION_LOAD
            std::string chapterCode = message.substr(chapterPrefix.size());
            if (chapterCode.find(':') == std::string::npos)
            {
                if (m_mission.empty())
                    std::cerr << "[ap] didn't find mission, return to menu and restart mission\n";
                chapterCode = m_mission + ":" + chapterCode;
            }
            std::cout << "[ap] chapter " << chapterCode << "\n";
            
            auto& chapters = haloap::GetChapterMap();
            auto chapterData = chapters.find(chapterCode);
            if (chapterData != chapters.end()) {
                std::cout << "[ap] Chapter: " << chapterData->second.name << "\n";
                SendLocation(chapterData->second.locationId);
            } else {
                std::cout << "[ap] Unknown chapter: " << chapterCode << "\n";
            }
            return true;
        }
        
        // "G_DEATH:<game>" the player died; "G_DEATH_LINKED:<game>" a received Death Link
        // killed them, which never counts or goes back out
        const std::string gDeathLinked = "G_DEATH_LINKED:", gDeath = "G_DEATH:";
        if (message.rfind(gDeathLinked, 0) == 0) {
            std::cout << "[deathlink] died from a received Death Link, not sent\n";
            return true;
        }
        if (message.rfind(gDeath, 0) == 0) {
            OnLocalDeath(std::atoi(message.c_str() + gDeath.size()));
            return true;
        }

        // H2 / H3 / H4 / Reach: "G_START:<game>:<map>", "G_CHAPTER:<game>:<map>:<key>",
        // "G_SKULL:<game>:<map>:<key>", "G_COMPLETE:<game>:<map>"
        const std::string gStart = "G_START:", gChapter = "G_CHAPTER:", gComplete = "G_COMPLETE:",
                          gSkull = "G_SKULL:";
        const bool isStart = message.rfind(gStart, 0) == 0;
        const bool isChapter = message.rfind(gChapter, 0) == 0;
        const bool isComplete = message.rfind(gComplete, 0) == 0;
        const bool isSkull = message.rfind(gSkull, 0) == 0;
        if (isStart || isChapter || isComplete || isSkull)
        {
            std::string rest = message.substr(message.find(':') + 1);
            std::vector<std::string> parts;
            for (size_t pos = 0;;) {
                size_t colon = rest.find(':', pos);
                parts.push_back(rest.substr(pos, colon == std::string::npos ? std::string::npos : colon - pos));
                if (colon == std::string::npos) break;
                pos = colon + 1;
            }
            if (parts.size() < ((isChapter || isSkull) ? 3u : 2u)) {
                std::cerr << "[ap] malformed: " << message << "\n";
                return true;
            }
            int code = std::atoi(parts[0].c_str());
            const GameMissionOrder* game = nullptr;
            for (const auto& order : GetGameMissionOrders())
                if (order.code == code) game = &order;
            int index = -1;
            if (game)
                for (size_t i = 0; i < game->missions.size(); i++)
                    if (_stricmp(game->missions[i].map, parts[1].c_str()) == 0) index = int(i);
            if (index < 0) {
                std::cerr << "[ap] unknown map for game " << code << ": " << parts[1] << "\n";
                return true;
            }
            const MissionDef& mission = game->missions[index];

            // After a win H2 and H3 load the next mission before the DLL's quit to the menu
            // lands; a locked one must not hand out its chapter card or anything else
            if (!IsMissionUnlocked(code, index, game->missions.size())) {
                std::cout << "[ap] " << mission.name << " is locked, ignoring: " << message << "\n";
                return true;
            }

            if (isStart) {
                std::cout << "[ap] game " << code << " mission start: " << mission.name << "\n";
                if (mission.startLocationId)
                    SendLocation(mission.startLocationId);
            }
            else if (isSkull) {
                // An exact key first; H2 skulls that aren't told apart match any pickup
                uint32_t key = uint32_t(std::strtol(parts[2].c_str(), nullptr, 10));
                const ChapterKeyDef* skull = nullptr;
                for (const auto& k : mission.skulls)
                    if (k.key == key) skull = &k;
                for (const auto& k : mission.skulls)
                    if (!skull && k.key == 0xFFFFFFFFu) skull = &k;
                if (skull) {
                    std::cout << "[ap] Skull: " << mission.name << " - " << skull->name << "\n";
                    SendLocation(skull->locationId);
                } else {
                    std::cout << "[ap] " << mission.name << ": skull " << parts[2] << " has no location\n";
                }
            }
            else if (isChapter) {
                uint32_t key = uint32_t(std::strtoul(parts[2].c_str(), nullptr, 10));
                const ChapterKeyDef* chapter = nullptr;
                for (const auto& c : mission.chapters)
                    if (c.key == key) chapter = &c;
                if (chapter) {
                    std::cout << "[ap] Chapter: " << mission.name << " - " << chapter->name << "\n";
                    SendLocation(chapter->locationId);
                } else {
                    std::cout << "[ap] " << mission.name << ": title " << key << " isn't a chapter\n";
                }
            }
            else {
                std::cout << "[ap] game " << code << " mission complete: " << mission.name << "\n";
                SendMissionChapters(code, index);
                auto final = m_finalByGame.find(code);
                if (final != m_finalByGame.end() && final->second == index)
                    OnFinalMissionComplete(code);
                else
                    SendLocation(int64_t(code) * 100000 + int64_t(index + 1) * 1000);
            }
            return true;
        }

        const std::string locationPrefix = "LOCATION_CHECKED: ";
        if (message.rfind(locationPrefix, 0) == 0)
        {
            int64_t locationId = std::stoll(message.substr(locationPrefix.size()));
            std::cout << "[ap] skull location checked: " << locationId << "\n";
            SendLocation(locationId);
            return true;
        }
        
        
        return false;
    }

    std::string APBridge::FinalsKey() const {
        return "halo_mcc_finals_" + std::to_string(m_client->get_team_number()) + "_" +
               std::to_string(m_client->get_player_number());
    }

    // The goal is the final mission of every enabled game. Which finals are done is kept
    // in the server's data storage so it survives reconnects.
    void APBridge::OnFinalMissionComplete(int code) {
        std::cout << "[ap] final mission of game " << code << " complete\n";
        {
            std::lock_guard<std::mutex> lock(m_checkedMutex);
            m_finalsDone.insert(code);
        }
        if (m_client && m_slotConnected.load())
            m_client->Set(FinalsKey(), nlohmann::json::array(), false,
                          { { "update", nlohmann::json::array({ code }) } });
        CheckGoal();
    }

    void APBridge::CheckGoal() {
        if (!m_client || !m_slotConnected.load()) return;
        std::lock_guard<std::mutex> lock(m_checkedMutex);
        // Pre-1.3 slot data: CE only
        std::set<int> needed;
        for (const auto& [code, idx] : m_finalByGame) needed.insert(code);
        if (needed.empty()) needed.insert(1);
        for (int code : needed)
            if (!m_finalsDone.count(code)) {
                std::cout << "[ap] goal: " << m_finalsDone.size() << "/" << needed.size()
                          << " final missions done\n";
                return;
            }
        std::cout << "[ap] *** all final missions complete: goal ***\n";
        m_client->StatusUpdate(APClient::ClientStatus::GOAL);
    }

    void APBridge::SendLocation(int64_t locationId) {
        if (!m_client) return;
        if (!m_slotConnected.load())
            std::cerr << "[ap] not connected to the slot, location " << locationId
                      << " is sent on reconnect\n";

        {
            std::lock_guard<std::mutex> lock(m_sentLocationsMutex);
            if (!m_sentLocations.insert(locationId).second) {
                std::cout << "[ap] location " << locationId << " already sent this session, skipping\n";
                return;
            }
        }

        // Queued by the client while the slot isn't connected
        std::list<int64_t> locs = { locationId };
        m_client->LocationChecks(locs);
        std::cout << "[ap] sent location check: " << locationId << "\n";
    
        // Track completion and notify DLL
        {
            std::lock_guard<std::mutex> lock(m_checkedMutex);
            m_checkedLocations.insert(locationId);
        }
        SendCompletionState();
    }

    void APBridge::SendMissionChapters(int code, int index) {
        if (code == 1) {
            const char* map = nullptr;
            for (const auto& [mapCode, i] : MISSION_CODE_TO_INDEX)
                if (i == index) map = mapCode.c_str();
            if (!map) return;
            const std::string prefix = std::string(map) + ":";
            for (const auto& [key, chapter] : GetChapterMap())
                if (key.rfind(prefix, 0) == 0)
                    SendLocation(chapter.locationId);
            return;
        }
        for (const auto& order : GetGameMissionOrders()) {
            if (order.code != code || index < 0 || index >= int(order.missions.size())) continue;
            const MissionDef& mission = order.missions[index];
            if (mission.startLocationId)
                SendLocation(mission.startLocationId);
            for (const auto& chapter : mission.chapters)
                SendLocation(chapter.locationId);
        }
    }

    // -------- callbacks ---------

    void APBridge::OnSocketConnected() {
        m_socketConnected.store(true);
        std::cout << "[ap] socket connected\n";
    }

    void APBridge::OnSocketError(const std::string& error) {
        std::cerr << "[ap] socket error: " << error << "\n";
    }

    void APBridge::OnSocketDisconnected() {
        m_socketConnected.store(false);
        m_slotConnected.store(false);
        std::cout << "[ap] socket disconnected (will auto-reconnect)\n";
    }

    void APBridge::OnRoomInfo() {
        std::cout << "[ap] room info received; attempting slot connect...\n";
        // ConnectSlot params: slot name, password, items-handling flags, tags, version
        // Items handling 0b111 = all items (local, starting inventory, world items).
        // DeathLink is only known from slot data, so the first connect goes without it and
        // OnSlotConnected adds it; reconnects keep it
        m_client->ConnectSlot(m_slot, m_password, 0b111, ConnectTags(), { 1, 2, 0 });
    }

    void APBridge::OnSlotConnected(const nlohmann::json& slotData) {
        m_slotConnected.store(true);
        std::cout << "[ap] *** slot connected ***\n";
        if (!slotData.empty()) {
            std::cout << "[ap] slot data: " << slotData.dump() << "\n";
        }
    
        // Load already-checked locations from server
        {
            std::lock_guard<std::mutex> lock(m_checkedMutex);
            auto checked = m_client->get_checked_locations();
            for (int64_t locId : checked) {
                m_checkedLocations.insert(locId);
            }
        }

        // A check sent while the socket was already down (before the disconnect was seen)
        // never reached the server; send again whatever this session sent that it lacks
        {
            std::list<int64_t> resend;
            auto missing = m_client->get_missing_locations();
            {
                std::lock_guard<std::mutex> lock(m_sentLocationsMutex);
                for (int64_t locId : m_sentLocations)
                    if (missing.count(locId)) resend.push_back(locId);
            }
            if (!resend.empty()) {
                std::cout << "[ap] resending " << resend.size() << " location checks\n";
                m_client->LocationChecks(resend);
            }
        }
        
        if (slotData.contains("final_mission"))
        {
            // "" when CE isn't in the world
            auto it = MISSION_NAME_TO_INDEX.find(BareMissionName(slotData.at("final_mission").get<std::string>()));
            if (it != MISSION_NAME_TO_INDEX.end())
                m_finalMission = it->second;
        }

        // 1.3+: per-game finals and required counts, keyed by apworld game key
        m_finalByGame.clear();
        m_requiredByGame.clear();
        for (const auto& order : GetGameMissionOrders())
        {
            if (slotData.contains("final_missions") && slotData["final_missions"].contains(order.key))
            {
                std::string name = slotData["final_missions"][order.key].get<std::string>();
                std::string bare = BareMissionName(name);
                for (size_t i = 0; i < order.missions.size(); i++)
                    if (order.missions[i].name == bare) m_finalByGame[order.code] = int(i);
                if (!m_finalByGame.count(order.code))
                    std::cerr << "[ap] unknown final mission '" << name << "' for " << order.key << "\n";
            }
            if (slotData.contains("missions_required") && slotData["missions_required"].contains(order.key))
                m_requiredByGame[order.code] = slotData["missions_required"][order.key].get<int>();
        }
        
        if (slotData.contains("skullsanity"))
        {
            m_skullsanityTier = slotData["skullsanity"].get<int>();
        }

        m_deathLink.store(slotData.value("death_link", 0) != 0);
        m_deathLinkAmnesty = slotData.value("death_link_amnesty", 0);
        if (m_deathLink.load()) {
            m_client->ConnectUpdate(false, 0, true, ConnectTags());
            std::cout << "[deathlink] on, amnesty " << m_deathLinkAmnesty << "\n";
        }

        // Finals already done in earlier sessions, and deaths forgiven so far
        m_client->Get({ FinalsKey(), AmnestyKey() });

        SendCompletionState();
    }

    void APBridge::OnSlotRefused(const std::list<std::string>& reasons) {
        std::cerr << "[ap] slot refused:\n";
        for (const auto& r : reasons) {
            std::cerr << "  - " << r << "\n";
        }
    }

    void APBridge::OnItemsReceived(const std::list<APClient::NetworkItem>& items) {
        for (const auto& item : items) {
            std::string itemName = m_client->get_item_name(item.item, m_game);
            std::cout << "[ap] received item: " << itemName
                << " (id " << item.item << ")\n";

            // Buffer the item
            {
                std::lock_guard<std::mutex> lock(m_itemBufferMutex);
                m_itemBuffer.push_back(item.item);
            }

            // Forward to DLL if connected
            if (m_sendToDll) {
                m_sendToDll("ITEM_RECIVED: " + std::to_string(item.item));
            }
        }
    }

    std::list<std::string> APBridge::ConnectTags() const {
        if (m_deathLink.load()) return { "DeathLink" };
        return {};
    }

    std::string APBridge::AmnestyKey() const {
        return "halo_mcc_deathlink_amnesty_" + std::to_string(m_client->get_team_number()) + "_" +
               std::to_string(m_client->get_player_number());
    }

    void APBridge::OnBounced(const nlohmann::json& packet) {
        if (!m_deathLink.load()) return;
        auto tags = packet.find("tags");
        if (tags == packet.end() || !tags->is_array() ||
            std::find(tags->begin(), tags->end(), "DeathLink") == tags->end())
            return;
        auto data = packet.find("data");
        if (data == packet.end() || !data->is_object()) return;

        std::string source = data->value("source", "");
        // The server bounces our own Death Link back to us too
        if (source == m_slot) return;
        std::string cause = data->value("cause", "");
        std::cout << "[deathlink] received from " << source << (cause.empty() ? "" : ": " + cause) << "\n";
        if (m_sendToDll)
            m_sendToDll("DEATHLINK: " + source);
    }

    void APBridge::OnLocalDeath(int code) {
        if (!m_deathLink.load()) return;
        if (!m_client || !m_slotConnected.load()) {
            std::cerr << "[deathlink] died while not connected, not sent\n";
            return;
        }

        int forgiven;
        {
            std::lock_guard<std::mutex> lock(m_deathMutex);
            if (m_deathsForgiven < m_deathLinkAmnesty) {
                forgiven = ++m_deathsForgiven;
            } else {
                m_deathsForgiven = 0;
                forgiven = -1;
            }
            m_client->Set(AmnestyKey(), 0, false, { { "replace", m_deathsForgiven } });
        }
        if (forgiven >= 0) {
            std::cout << "[deathlink] death forgiven (" << forgiven << "/" << m_deathLinkAmnesty << ")\n";
            return;
        }

        std::string game = "Halo";
        for (const auto& order : GetGameMissionOrders())
            if (order.code == code) game = order.key;
        static const std::map<std::string, std::string> kGameNames = {
            { "ce", "Halo: Combat Evolved" }, { "h2", "Halo 2" }, { "h3", "Halo 3" },
            { "h4", "Halo 4" }, { "reach", "Halo: Reach" },
        };
        auto name = kGameNames.find(game);
        nlohmann::json data = {
            { "time", m_client->get_server_time() },
            { "source", m_slot },
            { "cause", m_slot + " died in " + (name != kGameNames.end() ? name->second : game) + "." },
        };
        m_client->Bounce(data, {}, {}, { "DeathLink" });
        std::cout << "[deathlink] sent: " << data["cause"].get<std::string>() << "\n";
    }

    void APBridge::OnPrintJson(const APClient::PrintJSONArgs& args) {
        // Render the message as plain text.
        std::string text;
        for (const auto& part : args.data) {
            text += part.text;
        }
        std::cout << "[ap chat] " << text << "\n";
    }

}  // namespace haloap