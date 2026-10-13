// Stands in for HaloAP.dll in launcher tests (tools/launcher_test.py): connects to the
// launcher's pipe, sends each stdin line as one message, and prints each message from the
// launcher as "<< message". EOF on stdin closes the pipe, which the launcher takes as MCC
// exiting.
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <iostream>
#include <string>
#include <thread>
#include "shared/common.h"

namespace {
    HANDLE g_pipe = INVALID_HANDLE_VALUE;

    bool Io(bool write, void* data, DWORD size)
    {
        char* p = static_cast<char*>(data);
        while (size > 0)
        {
            OVERLAPPED ov = {};
            ov.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
            DWORD done = 0;
            BOOL ok = write ? WriteFile(g_pipe, p, size, &done, &ov) : ReadFile(g_pipe, p, size, &done, &ov);
            if (!ok && GetLastError() != ERROR_IO_PENDING) { CloseHandle(ov.hEvent); return false; }
            ok = GetOverlappedResult(g_pipe, &ov, &done, TRUE);
            CloseHandle(ov.hEvent);
            if (!ok || done == 0) return false;
            p += done;
            size -= done;
        }
        return true;
    }

    void Reader()
    {
        for (;;)
        {
            uint32_t length = 0;
            if (!Io(false, &length, sizeof(length)) || length == 0 || length > haloap::kMaxMessageSize) break;
            std::string body(length, '\0');
            if (!Io(false, body.data(), length)) break;
            printf("<< %s\n", body.c_str());
            fflush(stdout);
        }
        printf("<< (pipe closed)\n");
        fflush(stdout);
    }
}

int main()
{
    for (int i = 0; i < 300 && g_pipe == INVALID_HANDLE_VALUE; i++)
    {
        g_pipe = CreateFileW(haloap::kPipeName, GENERIC_READ | GENERIC_WRITE, 0, nullptr,
                             OPEN_EXISTING, FILE_FLAG_OVERLAPPED, nullptr);
        if (g_pipe == INVALID_HANDLE_VALUE) Sleep(100);
    }
    if (g_pipe == INVALID_HANDLE_VALUE)
    {
        printf("!! couldn't connect to the launcher's pipe\n");
        return 1;
    }
    printf("!! connected\n");
    fflush(stdout);
    std::thread(Reader).detach();

    std::string line;
    while (std::getline(std::cin, line))
    {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        uint32_t length = uint32_t(line.size());
        if (!Io(true, &length, sizeof(length)) || !Io(true, line.data(), length))
        {
            printf("!! send failed\n");
            return 1;
        }
    }
    CloseHandle(g_pipe);
    return 0;
}
