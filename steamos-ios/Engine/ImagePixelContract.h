/* Shared diagnostic byte ordering, MIT. No CPU-generated production image. */
#ifndef MPC_IMAGE_PIXEL_CONTRACT_H
#define MPC_IMAGE_PIXEL_CONTRACT_H
#include <stdint.h>
enum { MPC_IMAGE_METAL_BGRA8 = 80, MPC_IMAGE_VIRTIO_BGRX8 = 2,
       MPC_IMAGE_VULKAN_BGRA8 = 44, MPC_IMAGE_DRM_XRGB8 = 875713112 };
static inline unsigned mpc_pattern_phase(const unsigned char *p, int bgra) {
    unsigned blue = p[bgra ? 0 : 2];
    return blue == 165 ? 0 : blue == (165 ^ 41) ? 41 : 999;
}
static inline int mpc_pattern_matches(const unsigned char *p, unsigned x, unsigned y,
                                     unsigned phase, int bgra) {
    return (phase == 0 || phase == 41) && p[bgra ? 2 : 0] == ((x + phase) & 255) &&
           p[1] == ((y + phase) & 255) && p[bgra ? 0 : 2] == ((165 ^ phase) & 255) && p[3] == 255;
}
#endif
