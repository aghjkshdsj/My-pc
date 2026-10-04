/* Synthetic colour-order fixtures, never device/GPU proof. MIT. */
#include <assert.h>
#include <stdio.h>
#include "../Engine/ImagePixelContract.h"
int main(void) {
    unsigned checks = 0;
    for (unsigned pass = 0; pass < 2; ++pass) {
        unsigned phase = pass ? 41 : 0;
        uint64_t sum = 0;
        for (unsigned y = 0; y < 720; ++y) for (unsigned x = 0; x < 1280; ++x) {
            unsigned char rgba[4] = {(x + phase) & 255, (y + phase) & 255, 165 ^ phase, 255};
            unsigned char bgra[4] = {rgba[2], rgba[1], rgba[0], rgba[3]};
            assert(mpc_pattern_phase(bgra, 1) == phase);
            assert(mpc_pattern_matches(bgra, x, y, phase, 1));
            assert(mpc_pattern_matches(rgba, x, y, phase, 0));
            if (rgba[0] != rgba[2]) {
                assert(!mpc_pattern_matches(rgba, x, y, phase, 1));
                assert(!mpc_pattern_matches(bgra, x, y, phase, 0));
            }
            bgra[3] = 0;
            assert(!mpc_pattern_matches(bgra, x, y, phase, 1));
            assert(!mpc_pattern_matches(rgba, x, y, 999, 0));
            sum += rgba[0] + rgba[1] + rgba[2] + rgba[3];
            checks++;
        }
        assert(sum == (phase ? UINT64_C(603566080) : UINT64_C(615690240)));
    }
    printf("IMAGE_PIXEL_CONTRACT_OK pixels=%u; swapped channels rejected, synthetic fixtures only\n", checks);
    return 0;
}
