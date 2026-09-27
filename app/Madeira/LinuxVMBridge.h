#ifndef MY_PC_LINUX_VM_BRIDGE_H
#define MY_PC_LINUX_VM_BRIDGE_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* BGRA8888, callback-scoped buffer. Copy before returning; never block for UI. */
typedef void (*spc_linux_frame_callback)(void *context, const void *pixels,
                                       int width, int height, int stride);
/* Blocking entry point. Call on a dedicated thread, once per app process.
 * The caller owns argv for the entire session. Stop through QMP, not thread
 * cancellation. A completed/failed VM requires an app restart before reuse.
 * Returns QEMU exit status or -1 with an error for preflight/load failures.
 */
int spc_linux_run(const char *library, int argc, char **argv,
                  spc_linux_frame_callback frame, void *context,
                  char *error, size_t error_capacity);
#ifdef __cplusplus
}
#endif
#endif
