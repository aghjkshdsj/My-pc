// SPDX-License-Identifier: MIT
// Kernel/device bring-up only: mapped guest memory is not a GPU shader draw.
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>
#include <drm/drm.h>
#include <drm/virtgpu_drm.h>
#include <linux/virtio_gpu.h>

static char nonce[65] = "missing";
static const char *stage = "read-nonce";
static int saved_errno;
static uint64_t params[9];
static int supported[9];

static int read_nonce(void) {
    char line[4096];
    FILE *stream = fopen("/proc/cmdline", "r");
    if (!stream) return -1;
    int ok = fgets(line, sizeof(line), stream) != NULL;
    fclose(stream);
    if (!ok) return -1;
    char *token, *save = NULL;
    for (token = strtok_r(line, " \n", &save); token; token = strtok_r(NULL, " \n", &save)) {
        if (strncmp(token, "mpc_run=", 8) != 0) continue;
        const char *value = token + 8;
        size_t length = strlen(value);
        if (length != 32 || strspn(value, "0123456789abcdef") != length) return -1;
        memcpy(nonce, value, length + 1);
        return 0;
    }
    return -1;
}

static int getparam(int fd, uint64_t parameter, uint64_t *value) {
    struct drm_virtgpu_getparam request = {.param = parameter, .value = (uintptr_t)value};
    return ioctl(fd, DRM_IOCTL_VIRTGPU_GETPARAM, &request);
}

static int check(int status, const char *next_stage) {
    if (status < 0) { saved_errno = errno; return -1; }
    stage = next_stage;
    return 0;
}

int main(void) {
    int fd = -1, result = 1, mapped = 0, transferred = 0, closed = 0;
    void *memory = MAP_FAILED;
    const uint32_t width = 1280, height = 720;
    const size_t bytes = (size_t)width * height * 4;
    uint64_t sum = 0;
    uint32_t mismatches = 0, resource = 0, handle = 0;
    char driver[64] = {0};
    struct utsname system_info = {0};
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    uname(&system_info);
    if (read_nonce() != 0) { saved_errno = EINVAL; goto done; }
    stage = "open-drm";
    // Plain 2D virtio-gpu need not expose a render node. No master/KMS takeover.
    fd = open("/dev/dri/renderD128", O_RDWR | O_CLOEXEC);
    if (fd < 0) fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (check(fd, "driver-version") < 0) goto done;
    struct drm_version version = {.name_len = sizeof(driver) - 1, .name = driver};
    if (check(ioctl(fd, DRM_IOCTL_VERSION, &version), "verify-driver") < 0) goto done;
    if (strcmp(driver, "virtio_gpu") != 0) { saved_errno = ENODEV; goto done; }
    stage = "get-parameters";
    for (unsigned i = 1; i < 9; ++i) supported[i] = getparam(fd, i, &params[i]) == 0;
    if (!supported[VIRTGPU_PARAM_CAPSET_QUERY_FIX] || !params[VIRTGPU_PARAM_CAPSET_QUERY_FIX]) {
        saved_errno = ENOTSUP; goto done;
    }
    stage = "create-resource";
    struct drm_virtgpu_resource_create create = {
        .target = 2, .format = VIRTIO_GPU_FORMAT_B8G8R8X8_UNORM,
        .width = width, .height = height, .depth = 1, .array_size = 1,
        .size = bytes, .stride = width * 4
    };
    if (check(ioctl(fd, DRM_IOCTL_VIRTGPU_RESOURCE_CREATE, &create), "resource-info") < 0) goto done;
    handle = create.bo_handle; resource = create.res_handle;
    struct drm_virtgpu_resource_info info = {.bo_handle = handle};
    if (check(ioctl(fd, DRM_IOCTL_VIRTGPU_RESOURCE_INFO, &info), "verify-resource") < 0) goto done;
    if (!handle || !resource || info.res_handle != resource || info.size < bytes) {
        saved_errno = EINVAL; goto done;
    }
    stage = "map-offset";
    struct drm_virtgpu_map map = {.handle = handle};
    if (check(ioctl(fd, DRM_IOCTL_VIRTGPU_MAP, &map), "mmap-resource") < 0) goto done;
    memory = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, (off_t)map.offset);
    if (memory == MAP_FAILED) { saved_errno = errno; goto done; }
    unsigned char *pixels = memory;
    for (size_t i = 0; i < bytes; ++i) pixels[i] = (unsigned char)((i * 13 + 29) & 255);
    for (size_t i = 0; i < bytes; ++i) {
        unsigned char expected = (unsigned char)((i * 13 + 29) & 255);
        sum += pixels[i];
        mismatches += pixels[i] != expected;
    }
    mapped = mismatches == 0 && sum == UINT64_C(470016000);
    if (!mapped) { stage = "mapped-pattern"; saved_errno = EIO; goto done; }
    stage = "transfer-to-host";
    struct drm_virtgpu_3d_transfer_to_host upload = {
        .bo_handle = handle, .box = {.w = width, .h = height, .d = 1}
    };
    if (check(ioctl(fd, DRM_IOCTL_VIRTGPU_TRANSFER_TO_HOST, &upload), "wait-resource") < 0) goto done;
    struct drm_virtgpu_3d_wait wait = {.handle = handle};
    if (check(ioctl(fd, DRM_IOCTL_VIRTGPU_WAIT, &wait), "unmap-resource") < 0) goto done;
    // A successful transfer ioctl is not independent proof of host pixel contents.
    transferred = 1;
    if (check(munmap(memory, bytes), "close-resource") < 0) goto done;
    memory = MAP_FAILED;
    struct drm_gem_close release = {.handle = handle};
    if (check(ioctl(fd, DRM_IOCTL_GEM_CLOSE, &release), "complete") < 0) goto done;
    handle = 0; closed = 1; result = 0;
done:
    if (memory != MAP_FAILED) munmap(memory, bytes);
    if (handle && fd >= 0) {
        struct drm_gem_close release = {.handle = handle};
        ioctl(fd, DRM_IOCTL_GEM_CLOSE, &release);
    }
    if (fd >= 0) close(fd);
    clock_gettime(CLOCK_MONOTONIC, &end);
    double elapsed = (end.tv_sec - start.tv_sec) * 1000.0 + (end.tv_nsec - start.tv_nsec) / 1e6;
    printf("MPC_GPU_KERNEL {\"schema\":1,\"scope\":\"linux-virtio-gpu-kernel-device\","
           "\"run\":\"%s\",\"machine\":\"%s\",\"kernel\":\"%s\",\"driver\":\"%s\","
           "\"stage\":\"%s\",\"exit_code\":%d,\"errno\":%d,\"page_bytes\":%ld,"
           "\"width\":%u,\"height\":%u,\"mapped_bytes\":%zu,\"mapped_sum\":%" PRIu64 ","
           "\"mismatches\":%u,\"mapped_resource_verified\":%s,\"transfer_ioctl_completed\":%s,"
           "\"resource_closed\":%s,\"wall_ms\":%.3f,\"parameters\":{",
           nonce, system_info.machine, system_info.release, driver, stage, result, saved_errno,
           sysconf(_SC_PAGESIZE), width, height, bytes, sum, mismatches,
           mapped ? "true" : "false", transferred ? "true" : "false", closed ? "true" : "false", elapsed);
    for (unsigned i = 1; i < 9; ++i) {
        printf("%s\"%u\":{\"supported\":%s,\"value\":%" PRIu64 "}",
               i == 1 ? "" : ",", i, supported[i] ? "true" : "false", params[i]);
    }
    printf("},\"gpu_shader_verified\":false,\"host_pixels_verified\":false,"
           "\"metal_verified\":false,\"presentation_verified\":false,\"gameplay_verified\":false}\n");
    fflush(stdout);
    return result;
}
