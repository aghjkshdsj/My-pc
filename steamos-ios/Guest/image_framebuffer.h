/* Linux 6.12.111 virtio primary plane accepts XRGB8888. MIT. */
#ifndef MPC_IMAGE_FRAMEBUFFER_H
#define MPC_IMAGE_FRAMEBUFFER_H
#include <xf86drmMode.h>
#include <drm_fourcc.h>
static inline int mpc_add_image_framebuffer(int fd, uint32_t width, uint32_t height,
        uint32_t handle, uint32_t pitch, uint32_t offset, uint32_t *framebuffer) {
    uint32_t handles[4] = {handle}, pitches[4] = {pitch}, offsets[4] = {offset};
    /* BGRA Vulkan bytes, opaque alpha; X ignores the alpha byte on scanout.
     * Do not relabel RGBA storage, or use cursor-only ARGB on the primary. */
    return drmModeAddFB2(fd, width, height, DRM_FORMAT_XRGB8888,
                        handles, pitches, offsets, framebuffer, 0);
}
#endif
