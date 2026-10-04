/* Fresh MIT observer included once at the actual upstream queue commit site.
 * No command buffer, encoder, marker draw, wait or success override is added. */
#ifndef MPC_MOLTENVK_GUEST_TRACE_H
#define MPC_MOLTENVK_GUEST_TRACE_H
#include "MetalGuestTraceABI.h"
#include <mutex>

static std::mutex mpcGuestTraceLock;
static MPCMetalGuestTraceCallback mpcGuestTraceCallback = nullptr;
static void *mpcGuestTraceContext = nullptr;

extern "C" __attribute__((visibility("default")))
uint32_t mpc_mvk_configure_guest_trace(uint32_t abi,
    MPCMetalGuestTraceCallback callback, void *context)
{
    if (abi != MPC_METAL_TRACE_ABI || (callback && !context)) return 0;
    std::lock_guard<std::mutex> lock(mpcGuestTraceLock);
    mpcGuestTraceContext = context;
    mpcGuestTraceCallback = callback;
    return MPC_METAL_TRACE_ABI;
}

static void mpcObserveGuestMetalCommit(id<MTLCommandBuffer> buffer)
{
    if (!buffer) return;
    MPCMetalGuestTraceCallback callback;
    void *context;
    {
        std::lock_guard<std::mutex> lock(mpcGuestTraceLock);
        callback = mpcGuestTraceCallback;
        context = mpcGuestTraceContext;
    }
    if (!callback) return;
    id<MTLDevice> device = buffer.commandQueue.device;
    uint64_t token = callback(context, MPC_METAL_TRACE_OBSERVE_COMMIT, 0,
        (uint32_t)buffer.status, buffer.error != nil, (int64_t)buffer.error.code,
        device.registryID, device.name.UTF8String, 0.0, 0.0);
    if (!token) return;
    [buffer addCompletedHandler:^(id<MTLCommandBuffer> completed) {
        id<MTLDevice> actualDevice = completed.commandQueue.device;
        callback(context, MPC_METAL_TRACE_OBSERVE_COMPLETION, token,
            (uint32_t)completed.status, completed.error != nil,
            (int64_t)completed.error.code, actualDevice.registryID,
            actualDevice.name.UTF8String, completed.GPUStartTime, completed.GPUEndTime);
    }];
}
#endif
