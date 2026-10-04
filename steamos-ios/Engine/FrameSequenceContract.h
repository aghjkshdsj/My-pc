/* Fresh bounded diagnostic contract, MIT. No host-generated production image. */
#pragma once
#include "ImagePixelContract.h"
enum { MPC_FRAME_COUNT = 8, MPC_FRAME_PHASE_STEP = 17 };
static inline unsigned mpc_frame_phase(unsigned index) {
    return index < MPC_FRAME_COUNT ? index * MPC_FRAME_PHASE_STEP : 999;
}
static inline int mpc_frame_pattern_matches(const unsigned char *p, unsigned x, unsigned y,
                                           unsigned phase, int bgra) {
    return phase <= mpc_frame_phase(MPC_FRAME_COUNT-1) && phase % MPC_FRAME_PHASE_STEP == 0 &&
        p[bgra ? 2 : 0] == ((x+phase)&255) && p[1] == ((y+phase)&255) &&
        p[bgra ? 0 : 2] == ((165^phase)&255) && p[3] == 255;
}
