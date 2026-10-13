#pragma once

#include <apclient.hpp>
#include <memory>
#include <string>
#include <atomic>
#include <mutex>
#include <map>
#include <set>
#include <vector>
#include <cstdint>

namespace haloap {

    class APBridge {
    public:
        APBridge();
        ~APBridge();

        // Start connecting to an AP server. Non-blocking; poll() to make progress.
        // Returns false only if the client couldn't be constructed (bad params, etc.).
        bool Start(const std::string& serverUri,
            const std::string& game,
            const std::string& slot,
            const std::string& password);

        // Must be called regularly (e.g. every 50ms) to service the socket.
        void Poll();

        // Shut down. Safe to call multiple times.
        void Stop();

        // Queue a message from the DLL (forwarded from the pipe). It's handled on the next
        // Poll(), so the AP client is only ever used from the poll thread.
        void QueueDllMessage(const std::string& message);

        // Handle a message from the DLL. Only call from the poll thread.
        // Returns true if the message was recognized and handled.
        bool HandleDllMessage(const std::string& message);

        // Convenience: send a location check. Deduplicates within this session. While the
        // slot isn't connected the client queues it and sends it on the next connect.
        void SendLocation(int64_t locationId);

        // Sends a mission's chapter (and mission start) locations; on a win, so a card the
        // hook missed (a skipped cutscene) still counts
        void SendMissionChapters(int code, int index);
        // The mission's loadLocationIds (mission_order.h) that this seed has
        void SendLoadLocations(int code, int index);
        bool SeedHasLocation(int64_t locationId);

        bool IsConnected() const { return m_slotConnected.load(); }
        bool IsSocketConnected() const { return m_socketConnected.load(); }
        
        void SetSendToDll(std::function<void(const std::string&)> fn) {
            m_sendToDll = std::move(fn);
        }
        
        void ReplayBufferedItems();

    private:
        // APClient callbacks. These run on the poll thread.
        void OnSocketConnected();
        void OnSocketError(const std::string& error);
        void OnSocketDisconnected();
        void OnRoomInfo();
        void OnSlotConnected(const nlohmann::json& slotData);
        void OnSlotRefused(const std::list<std::string>& reasons);
        void OnItemsReceived(const std::list<APClient::NetworkItem>& items);
        void OnPrintJson(const APClient::PrintJSONArgs& args);
        void SendCompletionState();
        bool IsMissionUnlocked(int code, int index, size_t missionCount);
        void OnFinalMissionComplete(int code);
        void CheckGoal();
        std::string FinalsKey() const;

        // Death Link. The DLL reports each death as natural (G_DEATH) or caused by a
        // received link (G_DEATH_LINKED); only natural ones count toward the amnesty or
        // go out. Our own bounces come back from the server and are ignored.
        void OnBounced(const nlohmann::json& packet);
        void OnLocalDeath(int code);
        std::list<std::string> ConnectTags() const;
        std::string AmnestyKey() const;
        std::atomic<bool> m_deathLink{ false };
        int m_deathLinkAmnesty{ 0 };
        int m_deathsForgiven{ 0 };  // natural deaths since the last one sent; kept on the server
        std::mutex m_deathMutex;
        std::set<int> m_finalsDone;  // game codes whose final mission is done
        
        std::function<void(const std::string&)> m_sendToDll;

        std::unique_ptr<APClient> m_client;
        std::string m_game;
        std::string m_slot;
        std::string m_password;
        
        std::mutex m_itemBufferMutex;
        std::vector<int64_t> m_itemBuffer;
        int m_skullsanityTier{ -1 };
        // By game code; empty for pre-1.3 slot data (CE only, final needs all others)
        std::map<int, int> m_finalByGame;
        std::map<int, int> m_requiredByGame;

        std::atomic<bool> m_socketConnected{ false };
        std::atomic<bool> m_slotConnected{ false };
        std::atomic<bool> m_stopped{ false };

        // Locations we've sent this session, for deduplication.
        std::mutex m_sentLocationsMutex;
        std::set<int64_t> m_sentLocations;
        
        std::set<int64_t> m_checkedLocations;
        std::mutex m_checkedMutex;

        // DLL messages waiting for the poll thread
        std::mutex m_dllQueueMutex;
        std::vector<std::string> m_dllQueue;
    };

}  // namespace haloap