/* Fresh standard DRM atomic control, MIT. CPU dumb pixels are NOT GPU proof. */
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <linux/sync_file.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_fourcc.h>

enum { WIDTH = 1280, HEIGHT = 720, BUFFERS = 3, FLIPS = 6 };
typedef struct { uint32_t handle, fb, pitch; uint64_t bytes; void *map; } Buffer;
typedef struct {
    int fd, master, active;
    uint32_t connector, crtc, plane, blob;
    uint32_t connector_crtc, crtc_mode, crtc_active, out_fence, in_fence;
    uint32_t fb, plane_crtc, sx, sy, sw, sh, cx, cy, cw, ch;
    drmModeModeInfo mode;
    Buffer buffers[BUFFERS];
    unsigned events, sequence, sec, usec, expected_crtc;
    int unexpected_event;
} Output;

static uint32_t property(int fd, uint32_t object, uint32_t type,
                         const char *name, uint64_t *value) {
    drmModeObjectProperties *properties = drmModeObjectGetProperties(fd, object, type);
    uint32_t found = 0;
    if (!properties || properties->count_props > 256) goto done;
    for (uint32_t i = 0; i < properties->count_props; ++i) {
        drmModePropertyRes *p = drmModeGetProperty(fd, properties->props[i]);
        if (!p) continue;
        if (!strcmp(p->name, name)) {
            found = p->prop_id;
            if (value) *value = properties->prop_values[i];
        }
        drmModeFreeProperty(p);
        if (found) break;
    }
done:
    if (properties) drmModeFreeObjectProperties(properties);
    return found;
}

static int select_output(Output *o) {
    drmModeRes *r = drmModeGetResources(o->fd);
    if (!r || r->count_connectors < 1 || r->count_connectors > 16 ||
        r->count_crtcs < 1 || r->count_crtcs > 32) {
        if (r) drmModeFreeResources(r);
        return -1;
    }
    unsigned crtc_index = 32;
    for (int c = 0; c < r->count_connectors && !o->connector; ++c) {
        drmModeConnector *conn = drmModeGetConnector(o->fd, r->connectors[c]);
        if (!conn) continue;
        if (conn->connection == DRM_MODE_CONNECTED && conn->count_modes > 0 &&
            conn->count_modes <= 128 && conn->count_encoders > 0 && conn->count_encoders <= 32) {
            for (int m = 0; m < conn->count_modes && !o->connector; ++m) {
                if (conn->modes[m].hdisplay != WIDTH || conn->modes[m].vdisplay != HEIGHT) continue;
                for (int e = 0; e < conn->count_encoders && !o->connector; ++e) {
                    drmModeEncoder *enc = drmModeGetEncoder(o->fd, conn->encoders[e]);
                    if (!enc) continue;
                    for (int n = 0; n < r->count_crtcs; ++n) {
                        if (!(enc->possible_crtcs & (1u << n))) continue;
                        crtc_index = (unsigned)n; o->crtc = r->crtcs[n];
                        o->connector = conn->connector_id; o->mode = conn->modes[m]; break;
                    }
                    drmModeFreeEncoder(enc);
                }
            }
        }
        drmModeFreeConnector(conn);
    }
    drmModeFreeResources(r);
    if (!o->connector || crtc_index >= 32) return -1;
    drmModePlaneRes *planes = drmModeGetPlaneResources(o->fd);
    if (!planes || planes->count_planes > 64) {
        if (planes) drmModeFreePlaneResources(planes);
        return -1;
    }
    for (uint32_t i = 0; i < planes->count_planes && !o->plane; ++i) {
        drmModePlane *p = drmModeGetPlane(o->fd, planes->planes[i]);
        if (!p) continue;
        uint64_t type = UINT64_MAX;
        int xrgb = 0;
        if (p->count_formats <= 256)
            for (uint32_t j = 0; j < p->count_formats; ++j) xrgb |= p->formats[j] == DRM_FORMAT_XRGB8888;
        if ((p->possible_crtcs & (1u << crtc_index)) && xrgb &&
            property(o->fd, p->plane_id, DRM_MODE_OBJECT_PLANE, "type", &type) &&
            type == DRM_PLANE_TYPE_PRIMARY) o->plane = p->plane_id;
        drmModeFreePlane(p);
    }
    drmModeFreePlaneResources(planes);
    if (!o->plane) return -1;
#define PROP(field, object, type, name) o->field = property(o->fd, object, type, name, NULL)
    PROP(connector_crtc, o->connector, DRM_MODE_OBJECT_CONNECTOR, "CRTC_ID");
    PROP(crtc_mode, o->crtc, DRM_MODE_OBJECT_CRTC, "MODE_ID");
    PROP(crtc_active, o->crtc, DRM_MODE_OBJECT_CRTC, "ACTIVE");
    PROP(out_fence, o->crtc, DRM_MODE_OBJECT_CRTC, "OUT_FENCE_PTR");
    PROP(in_fence, o->plane, DRM_MODE_OBJECT_PLANE, "IN_FENCE_FD");
    PROP(fb, o->plane, DRM_MODE_OBJECT_PLANE, "FB_ID");
    PROP(plane_crtc, o->plane, DRM_MODE_OBJECT_PLANE, "CRTC_ID");
    PROP(sx, o->plane, DRM_MODE_OBJECT_PLANE, "SRC_X");
    PROP(sy, o->plane, DRM_MODE_OBJECT_PLANE, "SRC_Y");
    PROP(sw, o->plane, DRM_MODE_OBJECT_PLANE, "SRC_W");
    PROP(sh, o->plane, DRM_MODE_OBJECT_PLANE, "SRC_H");
    PROP(cx, o->plane, DRM_MODE_OBJECT_PLANE, "CRTC_X");
    PROP(cy, o->plane, DRM_MODE_OBJECT_PLANE, "CRTC_Y");
    PROP(cw, o->plane, DRM_MODE_OBJECT_PLANE, "CRTC_W");
    PROP(ch, o->plane, DRM_MODE_OBJECT_PLANE, "CRTC_H");
#undef PROP
    return o->connector_crtc && o->crtc_mode && o->crtc_active && o->fb && o->plane_crtc &&
           o->sx && o->sy && o->sw && o->sh && o->cx && o->cy && o->cw && o->ch ? 0 : -1;
}

static int allocate(Output *o, Buffer *b, unsigned phase) {
    struct drm_mode_create_dumb create = {.width = WIDTH, .height = HEIGHT, .bpp = 32};
    if (drmIoctl(o->fd, DRM_IOCTL_MODE_CREATE_DUMB, &create)) return -1;
    b->handle = create.handle; b->pitch = create.pitch; b->bytes = create.size;
    if (b->pitch < WIDTH * 4u || b->pitch > 65536 || b->bytes < (uint64_t)b->pitch * HEIGHT ||
        b->bytes > 32u * 1024u * 1024u) return -1;
    uint32_t handles[4] = {b->handle}, pitches[4] = {b->pitch}, offsets[4] = {0};
    if (drmModeAddFB2(o->fd, WIDTH, HEIGHT, DRM_FORMAT_XRGB8888, handles, pitches, offsets, &b->fb, 0)) return -1;
    struct drm_mode_map_dumb map = {.handle = b->handle};
    if (drmIoctl(o->fd, DRM_IOCTL_MODE_MAP_DUMB, &map)) return -1;
    b->map = mmap(NULL, b->bytes, PROT_READ | PROT_WRITE, MAP_SHARED, o->fd, map.offset);
    if (b->map == MAP_FAILED) { b->map = NULL; return -1; }
    for (unsigned y = 0; y < HEIGHT; ++y) {
        uint32_t *row = (uint32_t *)((uint8_t *)b->map + y * b->pitch);
        for (unsigned x = 0; x < WIDTH; ++x) row[x] = 0xff000000u | ((x + phase * 41) % 256) << 16 |
                                                          ((y + phase * 29) % 256) << 8 | phase * 67;
    }
    return 0;
}

static int commit(Output *o, uint32_t framebuffer, uint32_t flags, int *fence,
                  int invalid_geometry, int disable, int invalid_input) {
    drmModeAtomicReq *request = drmModeAtomicAlloc();
    if (!request) { errno = ENOMEM; return -1; }
    int ok = 1;
#define ADD(object, prop, value) do { if (drmModeAtomicAddProperty(request, object, prop, value) < 0) ok = 0; } while (0)
    ADD(o->connector, o->connector_crtc, disable ? 0 : o->crtc);
    ADD(o->crtc, o->crtc_active, disable ? 0 : 1);
    ADD(o->crtc, o->crtc_mode, disable ? 0 : o->blob);
    ADD(o->plane, o->fb, disable ? 0 : framebuffer);
    ADD(o->plane, o->plane_crtc, disable ? 0 : o->crtc);
    if (!disable) {
        ADD(o->plane, o->sx, 0); ADD(o->plane, o->sy, 0);
        ADD(o->plane, o->sw, (uint64_t)WIDTH << 16); ADD(o->plane, o->sh, (uint64_t)HEIGHT << 16);
        ADD(o->plane, o->cx, 0); ADD(o->plane, o->cy, 0);
        ADD(o->plane, o->cw, invalid_geometry ? WIDTH + 17 : WIDTH); ADD(o->plane, o->ch, HEIGHT);
        if (invalid_input && o->in_fence) ADD(o->plane, o->in_fence, INT_MAX);
    }
    if (fence && o->out_fence) ADD(o->crtc, o->out_fence, (uintptr_t)fence);
#undef ADD
    int result = -1;
    if (ok) result = drmModeAtomicCommit(o->fd, request, flags, o);
    else errno = ENOMEM;
    int saved = errno;
    drmModeAtomicFree(request); errno = saved;
    return result;
}

static void flip(int fd, unsigned sequence, unsigned sec, unsigned usec, unsigned crtc, void *data) {
    Output *o = data;
    if (fd != o->fd || crtc != o->expected_crtc || o->events || usec >= 1000000) o->unexpected_event = 1;
    o->events++; o->sequence = sequence; o->sec = sec; o->usec = usec;
}
static int await_flip(Output *o) {
    struct pollfd p = {.fd = o->fd, .events = POLLIN};
    int ready;
    do { ready = poll(&p, 1, 3000); } while (ready < 0 && errno == EINTR);
    if (ready != 1 || p.revents != POLLIN) return -1;
    drmEventContext context = {.version = 3, .page_flip_handler2 = flip};
    if (drmHandleEvent(o->fd, &context)) return -1;
    return o->events == 1 && !o->unexpected_event ? 0 : -1;
}
static int fence_signaled(int fd) {
    struct pollfd p = {.fd = fd, .events = POLLIN};
    int ready;
    do { ready = poll(&p, 1, 3000); } while (ready < 0 && errno == EINTR);
    if (ready != 1 || p.revents != POLLIN) return 0;
    struct sync_file_info info = {0};
    return !ioctl(fd, SYNC_IOC_FILE_INFO, &info) && info.status == 1 && info.num_fences > 0;
}
static int cleanup(Output *o) {
    int good = 1;
    if (o->active) {
        if (commit(o, 0, DRM_MODE_ATOMIC_ALLOW_MODESET, NULL, 0, 1, 0)) good = 0;
        else o->active = 0;
    }
    /* On failure close the fd to drop all owned objects; never declare a clean drain. */
    if (!o->active) {
        for (unsigned i = 0; i < BUFFERS; ++i) {
            Buffer *b = &o->buffers[i];
            if (b->map && munmap(b->map, b->bytes)) good = 0;
            if (b->fb && drmModeRmFB(o->fd, b->fb)) good = 0;
            if (b->handle) {
                struct drm_mode_destroy_dumb destroy = {.handle = b->handle};
                if (drmIoctl(o->fd, DRM_IOCTL_MODE_DESTROY_DUMB, &destroy)) good = 0;
            }
        }
        if (o->blob && drmModeDestroyPropertyBlob(o->fd, o->blob)) good = 0;
    } else {
        for (unsigned i = 0; i < BUFFERS; ++i)
            if (o->buffers[i].map && munmap(o->buffers[i].map, o->buffers[i].bytes)) good = 0;
    }
    if (o->master && drmDropMaster(o->fd)) good = 0;
    if (o->fd >= 0 && close(o->fd)) good = 0;
    return good;
}

int main(void) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    const char *run = getenv("MPC_KMS_RUN");
    if (!run || strlen(run) != 32 || strspn(run, "0123456789abcdef") != 32) return 2;
    Output o = {.fd = -1};
    const char *stage = "open-drm";
    unsigned completed = 0, fences = 0;
    int result = 1, bad_geometry = 0, bad_input = 0, saved = 0, geometry_errno = 0, input_errno = 0;
    o.fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (o.fd < 0) goto done;
    stage = "drm-master";
    if (drmSetMaster(o.fd)) goto done;
    o.master = 1;
    stage = "atomic-client-cap";
    if (drmSetClientCap(o.fd, DRM_CLIENT_CAP_UNIVERSAL_PLANES, 1) ||
        drmSetClientCap(o.fd, DRM_CLIENT_CAP_ATOMIC, 1)) goto done;
    stage = "select-720p-primary";
    if (select_output(&o)) goto done;
    printf("MPC_KMS_CAPS {\"schema\":1,\"run\":\"%s\",\"connector\":%u,\"crtc\":%u,\"plane\":%u,"
           "\"width\":1280,\"height\":720,\"format\":\"XRGB8888\",\"in_fence_fd\":%s,\"out_fence_ptr\":%s,"
           "\"native_reader_dependency_verified\":false}\n", run, o.connector, o.crtc, o.plane,
           o.in_fence ? "true" : "false", o.out_fence ? "true" : "false");
    stage = "allocate-cpu-dumb";
    for (unsigned i = 0; i < BUFFERS; ++i) if (allocate(&o, &o.buffers[i], i)) goto done;
    if (drmModeCreatePropertyBlob(o.fd, &o.mode, sizeof(o.mode), &o.blob)) goto done;
    stage = "test-only-valid";
    if (commit(&o, o.buffers[0].fb, DRM_MODE_ATOMIC_TEST_ONLY | DRM_MODE_ATOMIC_ALLOW_MODESET, NULL, 0, 0, 0)) goto done;
    stage = "test-only-invalid-geometry";
    errno = 0;
    if (!commit(&o, o.buffers[0].fb, DRM_MODE_ATOMIC_TEST_ONLY | DRM_MODE_ATOMIC_ALLOW_MODESET, NULL, 1, 0, 0) ||
        (errno != EINVAL && errno != ERANGE)) goto done;
    geometry_errno = errno;
    bad_geometry = 1;
    if (o.in_fence) {
        stage = "test-only-invalid-input-fence";
        errno = 0;
        if (!commit(&o, o.buffers[0].fb, DRM_MODE_ATOMIC_TEST_ONLY | DRM_MODE_ATOMIC_ALLOW_MODESET, NULL, 0, 0, 1) ||
            (errno != EINVAL && errno != EBADF)) goto done;
        input_errno = errno;
        bad_input = 1;
    }
    stage = "blocking-modeset";
    if (commit(&o, o.buffers[0].fb, DRM_MODE_ATOMIC_ALLOW_MODESET, NULL, 0, 0, 0)) goto done;
    o.active = 1; o.expected_crtc = o.crtc;
    for (unsigned i = 0; i < FLIPS; ++i) {
        int fence = -1;
        o.events = 0;
        stage = "nonblocking-atomic-flip";
        if (commit(&o, o.buffers[(i + 1) % BUFFERS].fb,
                   DRM_MODE_ATOMIC_NONBLOCK | DRM_MODE_PAGE_FLIP_EVENT, &fence, 0, 0, 0)) {
            if (fence >= 0) close(fence);
            goto done;
        }
        stage = "atomic-flip-event";
        int event_ok = !await_flip(&o);
        int fence_ok = !o.out_fence || (fence >= 0 && fence_signaled(fence));
        if (fence >= 0) close(fence);
        if (!event_ok || !fence_ok) goto done;
        completed++; if (o.out_fence) fences++;
        printf("MPC_KMS_FLIP {\"schema\":1,\"run\":\"%s\",\"index\":%u,\"slot\":%u,\"crtc\":%u,"
               "\"event_sequence\":%u,\"event_sec\":%u,\"event_usec\":%u,\"out_fence_signaled\":%s,"
               "\"native_display_timestamp\":false,\"metal_completion_verified\":false}\n",
               run, completed, (i + 1) % BUFFERS, o.crtc, o.sequence, o.sec, o.usec,
               o.out_fence ? "true" : "false");
    }
    result = 0; stage = "complete";
done:
    saved = result ? errno : 0;
    int cleaned = cleanup(&o);
    if (!cleaned) { result = 1; stage = "cleanup-failed"; }
    printf("MPC_KMS_RESULT {\"schema\":1,\"run\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d,\"errno\":%d,"
           "\"buffers\":%u,\"flips\":%u,\"signaled_out_fences\":%u,\"invalid_geometry_rejected\":%s,"
           "\"invalid_geometry_errno\":%d,\"invalid_input_fence_errno\":%d,"
           "\"invalid_input_fence_rejected\":%s,\"cleaned\":%s,\"cpu_dumb_control\":true,"
           "\"native_reader_dependency_verified\":false,\"metal_verified\":false,\"desktop_verified\":false,"
           "\"game_fps_verified\":false}\n", run, stage, result, saved, result ? 0 : BUFFERS, completed, fences,
           bad_geometry ? "true" : "false", geometry_errno, input_errno,
           bad_input ? "true" : "false", cleaned ? "true" : "false");
    return result;
}
