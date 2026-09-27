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

static atomic_bool claimed = false;

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
    int flags = RTLD_NOW | RTLD_LOCAL;
#ifdef RTLD_FIRST
    flags |= RTLD_FIRST;
#endif
    void *handle = dlopen(library, flags);
    if (!handle) {
        snprintf(error, error_capacity, "Cannot load ARM64 Linux runtime: %s", dlerror());
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
        snprintf(error, error_capacity, "The bundled QEMU runtime has an incompatible ABI.");
        dlclose(handle);
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
