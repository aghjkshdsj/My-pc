#import "GuestMetalTrace.h"
#import <Metal/Metal.h>
#include "GuestMetalTraceLedger.h"
#include "../Engine/MetalGuestTraceABI.h"
#include <chrono>
#include <condition_variable>
#include <dlfcn.h>
#include <mutex>

static_assert(MTLCommandBufferStatusCompleted == 4, "Completion ABI changed");
namespace {
struct TraceState {
    std::mutex lock;
    std::condition_variable changed;
    MPCMetalTraceLedger ledger;
    MPCMetalGuestTraceConfigure configure = nullptr;
    std::string run;
    bool started = false, frozen = false;
};
TraceState state;
uint64_t observe(void *context, uint32_t event, uint64_t token, uint32_t status,
    uint32_t hasError, int64_t errorCode, uint64_t registry, const char *name,
    double start, double end)
{
    auto &trace = *static_cast<TraceState *>(context);
    std::lock_guard<std::mutex> lock(trace.lock);
    if (!trace.started || trace.frozen) return 0;
    if (event == MPC_METAL_TRACE_OBSERVE_COMMIT)
        return trace.ledger.observe(registry, name, hasError != 0);
    if (event == MPC_METAL_TRACE_OBSERVE_COMPLETION) {
        trace.ledger.complete(token, status, hasError != 0, errorCode, registry, name, start, end);
        trace.changed.notify_all();
    } else ++trace.ledger.unknown;
    return 0;
}
}

BOOL MPCGuestMetalTraceBegin(NSString *run, NSString *framework, NSError **error)
{
    std::lock_guard<std::mutex> lock(state.lock);
    if (state.started || run.length != 32) {
        if (error) *error = [NSError errorWithDomain:@"MPCMetalTrace" code:1
            userInfo:@{NSLocalizedDescriptionKey: @"Metal trace needs one fresh Linux process."}];
        return NO;
    }
    // Loaded only after the host has verified the exact framework code identity.
    void *library = dlopen(framework.fileSystemRepresentation, RTLD_NOW | RTLD_LOCAL);
    auto configure = library ? reinterpret_cast<MPCMetalGuestTraceConfigure>(
        dlsym(library, "mpc_mvk_configure_guest_trace")) : nullptr;
    if (!configure || configure(MPC_METAL_TRACE_ABI, observe, &state) != MPC_METAL_TRACE_ABI) {
        if (error) *error = [NSError errorWithDomain:@"MPCMetalTrace" code:2
            userInfo:@{NSLocalizedDescriptionKey: @"The verified guest Metal observer is unavailable."}];
        return NO;
    }
    // Keep the library and callback context alive for the full process lifetime.
    state.configure = configure; state.run = run.UTF8String; state.started = true;
    return YES;
}

NSDictionary *MPCGuestMetalTraceFinish(BOOL guestPixelsPassed)
{
    std::unique_lock<std::mutex> lock(state.lock);
    bool callbacksDrained = state.changed.wait_for(lock, std::chrono::seconds(2),
        [] { return state.ledger.pending() == 0; });
    if (state.configure) state.configure(MPC_METAL_TRACE_ABI, nullptr, nullptr);
    state.frozen = true;
    NSString *expected = MTLCreateSystemDefaultDevice().name ?: @"";
    bool accepted = state.started && callbacksDrained && state.ledger.accepted(expected.UTF8String);
    NSMutableArray *samples = [NSMutableArray array];
    for (const auto &entry : state.ledger.entries) {
        [samples addObject:@{@"token": @(entry.token), @"device_registry_id": @(entry.registry),
            @"device_name": [NSString stringWithUTF8String:entry.device.c_str()] ?: @"",
            @"completion_observed": @(entry.completed), @"status": @(entry.status),
            @"has_error": @(entry.error), @"error_code": @(entry.errorCode),
            @"gpu_start_seconds": std::isfinite(entry.start) ? @(entry.start) : NSNull.null,
            @"gpu_end_seconds": std::isfinite(entry.end) ? @(entry.end) : NSNull.null}];
    }
    return @{@"schema": @1, @"scope": @"native-moltenvk-guest-command-completion",
        @"abi": @(MPC_METAL_TRACE_ABI), @"run": [NSString stringWithUTF8String:state.run.c_str()] ?: @"",
        @"status": accepted ? @"passed" : @"incomplete", @"observer_configured": @(state.started),
        @"callback_source": @"MVKQueueCommandBufferSubmission::commitActiveMTLCommandBuffer",
        @"observed_commit_points": @(state.ledger.entries.size()), @"completed": @(state.ledger.entries.size() - state.ledger.pending()),
        @"pending": @(state.ledger.pending()), @"failed": @(state.ledger.failed()),
        @"timed_completions": @(state.ledger.timed()), @"callbacks_drained": @(callbacksDrained),
        @"overflow": @(state.ledger.overflow), @"unknown_callbacks": @(state.ledger.unknown),
        @"duplicate_callbacks": @(state.ledger.duplicates), @"identity_errors": @(state.ledger.identityErrors),
        @"initial_errors": @(state.ledger.initialErrors), @"invalid_timing": @(state.ledger.invalidTiming),
        @"expected_device_name": expected, @"samples": samples,
        @"adds_gpu_work": @NO, @"guest_pixels_passed": @(guestPixelsPassed),
        @"metal_host_verified": @(accepted && guestPixelsPassed), @"host_memory_import_verified": @NO,
        @"presentation_verified": @NO, @"gameplay_verified": @NO,
        @"limitation": @"Actual guest MoltenVK submission callbacks; timings are command-buffer observations, not game FPS. This does not prove zero-copy import or moving presentation."};
}
