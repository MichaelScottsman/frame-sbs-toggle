#include "openvr.h"
#include <chrono>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

struct State { bool parallel, crossed; float aspect; };
static vr::IVROverlay* api;
static void check(vr::EVROverlayError e) {
    if (e != vr::VROverlayError_None) throw std::runtime_error(api->GetOverlayErrorNameFromEnum(e));
}
static State read(vr::VROverlayHandle_t h) {
    State s{};
    check(api->GetOverlayFlag(h, vr::VROverlayFlags_SideBySide_Parallel, &s.parallel));
    check(api->GetOverlayFlag(h, vr::VROverlayFlags_SideBySide_Crossed, &s.crossed));
    check(api->GetOverlayTexelAspect(h, &s.aspect));
    return s;
}
static void apply(vr::VROverlayHandle_t h, State s) {
    check(api->SetOverlayFlag(h, vr::VROverlayFlags_SideBySide_Parallel, false));
    check(api->SetOverlayFlag(h, vr::VROverlayFlags_SideBySide_Crossed, false));
    check(api->SetOverlayTexelAspect(h, s.aspect));
    check(api->SetOverlayFlag(h, vr::VROverlayFlags_SideBySide_Parallel, s.parallel));
    check(api->SetOverlayFlag(h, vr::VROverlayFlags_SideBySide_Crossed, s.crossed));
}
static bool equal(State a, State b) {
    return a.parallel == b.parallel && a.crossed == b.crossed && std::fabs(a.aspect-b.aspect)<0.0001f;
}
int main(int argc, char** argv) {
    bool initialized=false;
    try {
        if (argc != 2 && argc != 6) throw std::runtime_error("Usage: overlay-helper KEY [EXPECTED_HANDLE PARALLEL CROSSED ASPECT]");
        vr::EVRInitError error;
        vr::VR_Init(&error, vr::VRApplication_Background);
        if(error != vr::VRInitError_None) throw std::runtime_error(vr::VR_GetVRInitErrorAsEnglishDescription(error));
        initialized=true; api=vr::VROverlay();
        if(!api) throw std::runtime_error("OpenVR overlay interface unavailable");
        vr::VROverlayHandle_t h;
        check(api->FindOverlay(argv[1], &h));
        State original=read(h);
        if(argc==6) {
            if(h!=std::stoull(argv[2])) throw std::runtime_error("Overlay was recreated; rerun the command");
            State wanted{std::stoi(argv[3])!=0, std::stoi(argv[4])!=0, std::stof(argv[5])};
            if(!std::isfinite(wanted.aspect) || wanted.aspect<=0) throw std::runtime_error("Invalid aspect");
            try {
                apply(h,wanted);
                for(int i=0;i<20;i++) {
                    if(!equal(read(h),wanted)) throw std::runtime_error("Stereo settings were rejected or reset by the compositor");
                    std::this_thread::sleep_for(std::chrono::milliseconds(100));
                }
                if(!equal(read(h),wanted)) throw std::runtime_error("Stereo settings were reset by the compositor");
            } catch(const std::exception& e) {
                std::string message=e.what();
                try { apply(h,original); if(!equal(read(h),original)) throw std::runtime_error("readback mismatch"); }
                catch(const std::exception& rollback) { throw std::runtime_error(message+"; rollback failed: "+rollback.what()); }
                throw std::runtime_error(message+"; original settings restored");
            }
        }
        State s=read(h);
        std::cout << "{\"handle\":\"" << h << "\",\"parallel\":" << s.parallel
                  << ",\"crossed\":" << s.crossed << ",\"aspect\":" << s.aspect
                  << ",\"visible\":" << api->IsOverlayVisible(h) << "}\n";
        vr::VR_Shutdown(); return 0;
    } catch(const std::exception& e) {
        std::cerr << e.what() << '\n';
        if(initialized) vr::VR_Shutdown();
        return 1;
    }
}
