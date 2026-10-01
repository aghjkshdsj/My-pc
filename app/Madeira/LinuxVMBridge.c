/* GPL-3.0-or-later. QEMU ABI verified against v10.0.12-utm source.
 * QEMU 10 exports void qemu_init(int,char**), int qemu_main_loop(void), and
 * void qemu_cleanup(int). Do not use the older UTM wrapper's signatures.
 */
#include "LinuxVMBridge.h"
#include <dlfcn.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#ifdef __APPLE__
#include <TargetConditionals.h>
#endif

static atomic_bool claimed = false;

static void close_providers(void **providers)
{
    for (int i = 1; i >= 0; --i) {
        if (providers[i]) dlclose(providers[i]);
    }
}

static int prepare_metal(const char *library, int argc, char **argv,
                         void **providers, char *error, size_t capacity)
{
    bool metal = false;
    for (int i = 1; i + 1 < argc; ++i) {
        if (!strcmp(argv[i], "-display") && !strncmp(argv[i + 1], "egl-headless", 12)) {
            metal = true;
        }
    }
    if (!metal) return 0;
    const char *end = strstr(library, "/qemu-aarch64-softmmu.framework/");
    if (!end || end - library >= PATH_MAX) {
        snprintf(error, capacity, "Cannot locate the bundled Metal graphics providers.");
        return -1;
    }
    const char *names[] = { "GLESv2", "EGL" };
    const char *symbols[][3] = {
        { "glGetString", "glReadPixels", "glClear" },
        { "eglGetProcAddress", "eglGetDisplay", "eglInitialize" }
    };
    int flags = RTLD_NOW | RTLD_LOCAL;
#ifdef RTLD_FIRST
    flags |= RTLD_FIRST;
#endif
    for (int i = 0; i < 2; ++i) {
        char path[PATH_MAX];
        int length = snprintf(path, sizeof(path), "%.*s/%s.framework/%s",
                              (int)(end - library), library, names[i], names[i]);
        if (length < 0 || (size_t)length >= sizeof(path)) {
            snprintf(error, capacity, "The bundled Metal provider path is too long.");
            return -1;
        }
        providers[i] = dlopen(path, flags);
        if (!providers[i]) {
            snprintf(error, capacity, "Cannot load Metal graphics provider %s: %s. Restart My-pc and choose Software.",
                     names[i], dlerror());
            return -1;
        }
        for (int j = 0; j < 3; ++j) {
            if (!dlsym(providers[i], symbols[i][j])) {
                snprintf(error, capacity, "Metal graphics provider %s is missing %s.", names[i], symbols[i][j]);
                return -1;
            }
        }
        /* Check the same framework spelling used by pinned libepoxy before
         * its fatal resolver runs. Never change process cwd or symbol scope. */
        char relative[128];
#if defined(__APPLE__) && TARGET_OS_OSX
        snprintf(relative, sizeof(relative), "%s.framework/Versions/Current/%s", names[i], names[i]);
#else
        snprintf(relative, sizeof(relative), "%s.framework/%s", names[i], names[i]);
#endif
        void *lookup = dlopen(relative, flags);
        if (!lookup) {
            snprintf(error, capacity, "Cannot resolve Metal graphics provider %s through the app's framework search path: %s.",
                     names[i], dlerror());
            return -1;
        }
        dlclose(lookup);
    }
    fprintf(stderr, "MYPC_METAL_PROVIDER_PREFLIGHT_OK\n");
    return 0;
}

int spc_linux_run(const char *library, int argc, char **argv,
                  spc_linux_frame_callback frame, void *context,
                  char *error, size_t error_capacity)
{
    if (!library || argc < 1 || !argv || !argv[0] || !error || !error_capacity) {
        return -1;
    }
    error[0] = 0;
    if (atomic_exchange(&claimed, true)) {
        snprintf(error, error_capacity, "Restart My-pc before starting another Linux session.");
        return -1;
    }
    void *providers[2] = { NULL, NULL };
    if (prepare_metal(library, argc, argv, providers, error, error_capacity)) {
        close_providers(providers);
        atomic_store(&claimed, false);
        return -1;
    }
    int flags = RTLD_NOW | RTLD_LOCAL;
#ifdef RTLD_FIRST
    flags |= RTLD_FIRST;
#endif
    void *handle = dlopen(library, flags);
    if (!handle) {
        snprintf(error, error_capacity, "Cannot load ARM64 Linux runtime: %s", dlerror());
        close_providers(providers);
        atomic_store(&claimed, false);
        return -1;
    }
    void (*initialize)(int, char **) = (void (*)(int, char **))dlsym(handle, "qemu_init");
    int (*run_loop)(void) = (int (*)(void))dlsym(handle, "qemu_main_loop");
    void (*cleanup)(int) = (void (*)(int))dlsym(handle, "qemu_cleanup");
    int (*display_start)(spc_linux_frame_callback, void *) =
        (int (*)(spc_linux_frame_callback, void *))dlsym(handle, "my_pc_display_start");
    void (*display_stop)(void) = (void (*)(void))dlsym(handle, "my_pc_display_stop");
    if (!initialize || !run_loop || !cleanup || (frame && (!display_start || !display_stop))) {
        snprintf(error, error_capacity,
                 "QEMU runtime is missing required exports:%s%s%s%s%s",
                 initialize ? "" : " qemu_init", run_loop ? "" : " qemu_main_loop",
                 cleanup ? "" : " qemu_cleanup",
                 !frame || display_start ? "" : " my_pc_display_start",
                 !frame || display_stop ? "" : " my_pc_display_stop");
        dlclose(handle);
        close_providers(providers);
        atomic_store(&claimed, false);
        return -1;
    }
    initialize(argc, argv);
    if (frame && display_start(frame, context) != 0) {
        snprintf(error, error_capacity, "Linux has no graphical console.");
        cleanup(1);
        return -1;
    }
    int status = run_loop();
    if (frame) {
        display_stop();
    }
    cleanup(status);
    /* QEMU and dependency globals/threads are not safe to unload or reinit.
     * Keep the handle until process exit, as we do with the Wine runtime. */
    if (status) {
        snprintf(error, error_capacity, "Linux runtime exited with status %d.", status);
    }
    return status;
}
