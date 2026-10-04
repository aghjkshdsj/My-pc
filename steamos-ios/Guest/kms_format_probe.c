/* Real guest-kernel framebuffer-format control. CPU allocation, no GPU proof. MIT. */
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <xf86drm.h>
#include "image_framebuffer.h"
int main(void) {
    const char *run = getenv("MPC_KMS_RUN");
    if (!run || strlen(run) != 32 || strspn(run, "0123456789abcdef") != 32) return 2;
    int fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (fd < 0) return 3;
    struct drm_mode_create_dumb dumb = {.width=1280, .height=720, .bpp=32};
    if (drmIoctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &dumb)) return 4;
    uint32_t handles[4] = {dumb.handle}, pitches[4] = {dumb.pitch}, offsets[4] = {0}, bad_fb = 0, fb = 0;
    errno = 0;
    int bad = drmModeAddFB2(fd, 1280, 720, DRM_FORMAT_ABGR8888, handles, pitches, offsets, &bad_fb, 0);
    int bad_errno = errno;
    if (!bad || bad_errno != ENOENT || bad_fb) return 5;
    if (mpc_add_image_framebuffer(fd, 1280, 720, dumb.handle, dumb.pitch, 0, &fb) || !fb) return 6;
    if (drmModeRmFB(fd, fb)) return 7;
    struct drm_mode_destroy_dumb destroy = {.handle=dumb.handle};
    if (drmIoctl(fd, DRM_IOCTL_MODE_DESTROY_DUMB, &destroy)) return 8;
    close(fd);
    printf("MPC_KMS_FORMAT_CONTROL {\"schema\":1,\"run\":\"%s\",\"abgr_errno\":%d,"
           "\"xrgb_framebuffer_created\":true,\"framebuffer_released\":true,"
           "\"scope\":\"linux-kernel-cpu-allocation-format-control\","
           "\"gpu_rendering_verified\":false,\"host_memory_import_verified\":false,\"presentation_verified\":false}\n",run,bad_errno);
    return 0;
}
