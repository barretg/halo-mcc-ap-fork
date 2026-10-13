#pragma once
#include "../pipe_client.h"

namespace haloap {

    // CE: MCC's mission segment reporter, which the mission scripts call through
    // (mcc_mission_segment "<name>") right before each cutscene, whether or not the player
    // then skips it. Sends "SEGMENT:<map>:<name>", so a chapter card inside a skippable
    // cutscene can still be sent.
    bool InstallMissionSegmentHook(PipeClient* pipe);
    void UninstallMissionSegmentHook();

}  // namespace haloap
