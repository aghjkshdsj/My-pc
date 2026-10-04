/* Fresh MIT diagnostic ABI. It observes existing MoltenVK work only. */
#ifndef MPC_METAL_GUEST_TRACE_ABI_H
#define MPC_METAL_GUEST_TRACE_ABI_H
#include <stdint.h>
#define MPC_METAL_TRACE_ABI 1u
#define MPC_METAL_TRACE_OBSERVE_COMMIT 0u
#define MPC_METAL_TRACE_OBSERVE_COMPLETION 1u
typedef uint64_t (*MPCMetalGuestTraceCallback)(void *context, uint32_t event,
    uint64_t token, uint32_t status, uint32_t has_error, int64_t error_code,
    uint64_t device_registry_id, const char *device_name,
    double gpu_start_seconds, double gpu_end_seconds);
typedef uint32_t (*MPCMetalGuestTraceConfigure)(uint32_t abi,
    MPCMetalGuestTraceCallback callback, void *context);
#endif
