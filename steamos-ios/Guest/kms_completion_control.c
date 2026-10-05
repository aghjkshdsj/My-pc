/* Fresh MIT test harness. Actual DRM ioctls; CPU dumb buffers, never GPU/FPS proof. */
#define main mpc_atomic_api_control_unused_main
#include "kms_atomic_gate.c"
#undef main

static int sync_status(int fd, int *status) {
    struct sync_file_info info = {0};
    if (ioctl(fd, SYNC_IOC_FILE_INFO, &info) || !info.num_fences) return -1;
    *status = info.status;
    return 0;
}

static int remain_pending(Output *o, int fence, int milliseconds) {
    struct pollfd p[2] = {{.fd = fence, .events = POLLIN}, {.fd = o->fd, .events = POLLIN}};
    int status = 99, ret;
    do { ret = poll(p, 2, milliseconds); } while (ret < 0 && errno == EINTR);
    return ret == 0 && !sync_status(fence, &status) && status == 0;
}

int main(void) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    const char *run = getenv("MPC_KMS_RUN"), *kind = getenv("MPC_COMPLETION_CASE");
    if (!run || strlen(run) != 32 || strspn(run, "0123456789abcdef") != 32 || !kind ||
        (strcmp(kind, "delayed") && strcmp(kind, "error") && strcmp(kind, "missing"))) return 2;
    Output o = {.fd = -1};
    int result = 1, fence = -1, status = 99, initial_status = 99;
    unsigned early_pending = 0, events = 0, positive = 0, failed = 0;
    const char *stage = "setup";
    o.fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (o.fd < 0 || drmSetMaster(o.fd)) goto done;
    o.master = 1;
    if (drmSetClientCap(o.fd, DRM_CLIENT_CAP_UNIVERSAL_PLANES, 1) ||
        drmSetClientCap(o.fd, DRM_CLIENT_CAP_ATOMIC, 1) || select_output(&o) ||
        !o.in_fence || !o.out_fence) goto done;
    for (unsigned i = 0; i < BUFFERS; ++i) if (allocate(&o, &o.buffers[i], i)) goto done;
    if (drmModeCreatePropertyBlob(o.fd, &o.mode, sizeof(o.mode), &o.blob)) goto done;
    stage = "initial-modeset-fence";
    if (commit(&o, o.buffers[0].fb, DRM_MODE_ATOMIC_ALLOW_MODESET, &fence, 0, 0, 0)) goto done;
    o.active = 1; o.expected_crtc = o.crtc;
    if (fence < 0 || sync_status(fence, &initial_status) || initial_status != 1) goto done;
    close(fence); fence = -1;
    for (unsigned i = 0; i < (!strcmp(kind, "delayed") ? 2u : 1u); ++i) {
        o.events = 0; stage = "nonblocking-submit";
        if (commit(&o, o.buffers[i + 1].fb, DRM_MODE_ATOMIC_NONBLOCK | DRM_MODE_PAGE_FLIP_EVENT,
                   &fence, 0, 0, 0) || fence < 0) goto done;
        stage = "no-50ms-release";
        if (!remain_pending(&o, fence, 100)) goto done;
        early_pending++;
        if (!strcmp(kind, "missing")) {
            stage = "missing-response-held";
            if (!remain_pending(&o, fence, 1500)) goto done;
            printf("MPC_COMPLETION_RESULT {\"schema\":1,\"run\":\"%s\",\"case\":\"missing\","
                   "\"stage\":\"missing-response-held\",\"initial_status\":%d,\"early_pending\":1,"
                   "\"events\":0,\"positive_fences\":0,\"error_fences\":0,\"last_status\":0,"
                   "\"buffers_retained\":true,\"cleaned\":false,\"cpu_dumb_control\":true,"
                   "\"metal_verified\":false,\"physical_iphone\":false}\n", run, initial_status);
            /* Intentionally retain all objects. The host ends this disposable test VM. */
            for (;;) pause();
        }
        stage = "exact-completion";
        if (await_flip(&o) || sync_status(fence, &status)) goto done;
        events++;
        if (!strcmp(kind, "error")) {
            if (status != -EIO) goto done;
            failed++;
        } else {
            if (status != 1) goto done;
            positive++;
        }
        close(fence); fence = -1;
    }
    result = 0; stage = "complete";
done:
    if (fence >= 0) close(fence);
    int cleaned = cleanup(&o);
    if (!cleaned) { result = 1; stage = "cleanup-failed"; }
    printf("MPC_COMPLETION_RESULT {\"schema\":1,\"run\":\"%s\",\"case\":\"%s\",\"stage\":\"%s\","
           "\"initial_status\":%d,\"early_pending\":%u,\"events\":%u,\"positive_fences\":%u,"
           "\"error_fences\":%u,\"last_status\":%d,\"buffers_retained\":false,\"cleaned\":%s,"
           "\"cpu_dumb_control\":true,\"metal_verified\":false,\"physical_iphone\":false}\n",
           run, kind, stage, initial_status, early_pending, events, positive, failed, status,
           cleaned ? "true" : "false");
    return result;
}
