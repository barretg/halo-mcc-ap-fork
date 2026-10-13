#include "debug_commands.h"
#include "pipe_client.h"
#include <cstdarg>
#include <windows.h>
#include <atomic>
#include <cstdio>
#include <cstdlib>

namespace haloap {

    namespace {
        // A command waits this long for a game thread: the mission may still be loading
        constexpr ULONGLONG kTimeoutMs = 60000;

        std::atomic<int> g_action{ int(DebugAction::None) };
        std::atomic<int> g_arg{ 0 };
        std::atomic<ULONGLONG> g_requestedAt{ 0 };
        PipeClient* g_pipe = nullptr;
    }

    void SetDebugPipe(PipeClient* pipe)
    {
        g_pipe = pipe;
    }

    void DebugReport(const char* format, ...)
    {
        char text[256];
        va_list args;
        va_start(args, format);
        vsnprintf(text, sizeof(text), format, args);
        va_end(args);
        printf("[debug] %s\n", text);
        if (g_pipe && g_pipe->IsConnected())
            g_pipe->SendAsync(std::string("DEBUG_RESULT: ") + text);
    }

    bool RequestDebugAction(const std::string& command)
    {
        DebugAction action;
        int arg = 0;
        if (command.rfind("title ", 0) == 0)
        {
            action = DebugAction::Title;
            arg = std::atoi(command.c_str() + 6);
        }
        else if (command == "win")
            action = DebugAction::Win;
        else
            return false;

        printf("[debug] requested: %s\n", command.c_str());
        g_arg.store(arg);
        g_action.store(int(action));
        g_requestedAt.store(GetTickCount64());
        return true;
    }

    DebugAction TakeDebugAction(int& arg)
    {
        int action = g_action.exchange(int(DebugAction::None));
        if (action == int(DebugAction::None))
            return DebugAction::None;
        if (GetTickCount64() - g_requestedAt.load() > kTimeoutMs)
        {
            DebugReport("not in a mission in time, dropped");
            return DebugAction::None;
        }
        arg = g_arg.load();
        return DebugAction(action);
    }

}  // namespace haloap
