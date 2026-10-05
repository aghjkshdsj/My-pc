/* Fresh bounded moving-output gate, MIT. No game/FPS proof. */
#pragma once
#include "ImagePixelContract.h"
enum { MPC_MOVING_BUFFERS = 3, MPC_MOVING_FRAMES = 120 };
static inline unsigned mpc_moving_phase(unsigned index) { return index < MPC_MOVING_FRAMES ? (index * 17u) % 120u : 999u; }
static inline int mpc_moving_endpoint(unsigned index) { return index == 0 || index == MPC_MOVING_FRAMES - 1; }
static inline int mpc_moving_pattern_matches(const unsigned char *p, unsigned x, unsigned y, unsigned phase, int bgra) {
    return phase < 120u && p[bgra ? 2 : 0] == ((x + phase) & 255u) &&
        p[1] == ((y + phase) & 255u) && p[bgra ? 0 : 2] == ((165u ^ phase) & 255u) && p[3] == 255u;
}
