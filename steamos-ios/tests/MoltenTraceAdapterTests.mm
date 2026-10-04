// Production observer ABI/lifecycle fixtures, not GPU or phone evidence.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cassert>
#include <cstring>
#include "MoltenVKGuestTrace.h"

@interface MPCFixtureDevice : NSObject
@property(nonatomic, readonly) uint64_t registryID;
@property(nonatomic, readonly) NSString *name;
@end
@implementation MPCFixtureDevice
- (uint64_t)registryID { return 99; }
- (NSString *)name { return @"fixture-device-not-a-GPU-result"; }
@end
@interface MPCFixtureQueue : NSObject
@property(nonatomic, strong) id<MTLDevice> device;
@end
@implementation MPCFixtureQueue
@end
@interface MPCFixtureBuffer : NSObject
@property(nonatomic, strong) id<MTLCommandQueue> commandQueue;
@property(nonatomic) MTLCommandBufferStatus status;
@property(nonatomic, strong) NSError *error;
@property(nonatomic) double GPUStartTime;
@property(nonatomic) double GPUEndTime;
@property(nonatomic, copy) MTLCommandBufferHandler handler;
- (void)addCompletedHandler:(MTLCommandBufferHandler)handler;
- (void)finishFixture;
@end
@implementation MPCFixtureBuffer
- (void)addCompletedHandler:(MTLCommandBufferHandler)handler { self.handler = handler; }
- (void)finishFixture {
    MTLCommandBufferHandler copy = self.handler; self.handler = nil;
    if (copy) copy((id<MTLCommandBuffer>)self);
}
@end

struct Events { unsigned calls = 0; uint64_t token = 7; uint32_t status = 0, error = 0;
    int64_t errorCode = 0; double start = 0, end = 0; };
static uint64_t observe(void *context, uint32_t event, uint64_t token, uint32_t status,
    uint32_t error, int64_t code, uint64_t registry, const char *name, double start, double end)
{
    auto &events = *static_cast<Events *>(context);
    assert(registry == 99 && !strcmp(name, "fixture-device-not-a-GPU-result"));
    ++events.calls;
    if (event == MPC_METAL_TRACE_OBSERVE_COMMIT) { assert(token == 0); return events.token; }
    assert(event == MPC_METAL_TRACE_OBSERVE_COMPLETION && token == events.token);
    events.status = status; events.error = error; events.errorCode = code;
    events.start = start; events.end = end;
    return 0;
}

int main()
{
    @autoreleasepool {
        Events events;
        auto device = [MPCFixtureDevice new]; auto queue = [MPCFixtureQueue new];
        queue.device = (id<MTLDevice>)device;
        auto buffer = [MPCFixtureBuffer new]; buffer.commandQueue = (id<MTLCommandQueue>)queue;
        mpcObserveGuestMetalCommit((id<MTLCommandBuffer>)buffer);
        assert(events.calls == 0 && buffer.handler == nil);
        assert(mpc_mvk_configure_guest_trace(2, observe, &events) == 0);
        assert(mpc_mvk_configure_guest_trace(1, observe, nullptr) == 0);
        assert(mpc_mvk_configure_guest_trace(1, observe, &events) == 1);
        mpcObserveGuestMetalCommit(nil); assert(events.calls == 0);
        mpcObserveGuestMetalCommit((id<MTLCommandBuffer>)buffer);
        assert(events.calls == 1 && buffer.handler != nil);
        // A configured callback is captured; disabling future observations must
        // not silently drop an already registered completion.
        assert(mpc_mvk_configure_guest_trace(1, nullptr, nullptr) == 1);
        buffer.status = MTLCommandBufferStatusCompleted; buffer.GPUStartTime = 3; buffer.GPUEndTime = 4;
        [buffer finishFixture];
        assert(events.calls == 2 && events.status == MTLCommandBufferStatusCompleted);
        assert(events.error == 0 && events.start == 3 && events.end == 4);
        events = Events{}; events.token = 0;
        assert(mpc_mvk_configure_guest_trace(1, observe, &events) == 1);
        mpcObserveGuestMetalCommit((id<MTLCommandBuffer>)buffer);
        assert(events.calls == 1 && buffer.handler == nil);
        events = Events{};
        mpcObserveGuestMetalCommit((id<MTLCommandBuffer>)buffer);
        buffer.status = MTLCommandBufferStatusError;
        buffer.error = [NSError errorWithDomain:@"fixture" code:23 userInfo:nil];
        [buffer finishFixture];
        assert(events.calls == 2 && events.status == MTLCommandBufferStatusError);
        assert(events.error == 1 && events.errorCode == 23);
        assert(mpc_mvk_configure_guest_trace(1, nullptr, nullptr) == 1);
        puts("METAL_TRACE_ADAPTER_FIXTURES_PASSED scope=ABI-and-callback-lifetime-only GPU-proof=false");
    }
}
