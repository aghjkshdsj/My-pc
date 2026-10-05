// Fresh MIT bridge. The UART is a bounded diagnostic protocol, not a compositor.
#import "MovingFrameTransport.h"
#import "GuestScreenPresentation.h"
#import "ProbeBridge.h"
#import <Metal/Metal.h>
#import <QuartzCore/QuartzCore.h>
#include "../Engine/FrameLeaseLedger.h"
#include "../Engine/FrameReleaseWire.h"
#include "../Engine/MovingFrameContract.h"
#include "../Engine/MovingFrameRefresh.h"
#include "GuestFrameBudget.h"
#include <atomic>
#include <dlfcn.h>
#include <fcntl.h>
#include <poll.h>
#include <sys/socket.h>
#include <thread>
#include <unistd.h>
#include <memory>
#include <string>

@interface MPCMovingContext : NSObject {
@public
    std::unique_ptr<mpc::FrameLeaseLedger> ledger;
    mpc::FrameSession session;
    std::thread reader;
    std::atomic<bool> readerExited;
}
@property(nonatomic, strong) dispatch_queue_t executor;
@property(nonatomic, strong) id<MTLCommandQueue> queue;
@property(nonatomic, strong) NSMutableArray *buffers, *offers, *releases, *acquires, *images, *events, *refreshes;
@property(nonatomic, copy) NSString *nonce;
@property(nonatomic) int hostFD, engineFD, logFD;
@property(nonatomic) uint64_t registry, sequence, generation, activeResource, nextFence;
@property(nonatomic) NSUInteger errors, readbacks, repeatedFlushes, replies;
@property(nonatomic) NSUInteger linearAlignment;
@property(nonatomic) BOOL transferred, active, finished, channelEOF, readerJoined;
@end
@implementation MPCMovingContext
@end
static MPCMovingContext *moving;

// All state-table methods and socket writes run on this executor. Engine and
// Metal callbacks never mutate the table directly and never hold its queue.
static void fault(MPCMovingContext *c, NSString *reason) {
    c.errors++; c->ledger->quarantine();
    MPCDiagnosticStage(@"linux-moving-rejected", @{@"reason": reason, @"errors": @(c.errors)});
}
static BOOL writeAll(int fd, const void *bytes, size_t count, BOOL socket) {
    auto *p = static_cast<const unsigned char *>(bytes);
    while (count) {
        ssize_t n = socket ? send(fd, p, count, 0) : write(fd, p, count);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return NO;
        p += n; count -= (size_t)n;
    }
    return YES;
}
static BOOL reply(MPCMovingContext *c, unsigned kind, const mpc::FrameTicket &ticket,
                  uint64_t release, uint32_t status) {
    MPCReleaseMessage message = {c->session.high, c->session.low, ticket.serial, ticket.incarnation,
        release, c.registry, ticket.resource, status, kind};
    unsigned char wire[MPC_RELEASE_WIRE_BYTES];
    if (!mpc_wire_encode(&message, wire, sizeof(wire)) || !writeAll(c.hostFD, wire, sizeof(wire), YES)) {
        fault(c, @"channel-reply-write"); return NO;
    }
    c.replies++; return YES;
}
static NSMutableDictionary *bufferFor(MPCMovingContext *c, uint32_t resource) {
    for (NSMutableDictionary *row in c.buffers)
        if ([row[@"resource_id"] unsignedIntValue] == resource) return row;
    return nil;
}
static mpc::FrameTicket ticketFor(MPCMovingContext *c, NSDictionary *row) {
    return {c->session, [row[@"serial"] unsignedLongLongValue], [row[@"incarnation"] unsignedLongLongValue],
        [row[@"resource_id"] unsignedIntValue]};
}
static void releaseConsumer(MPCMovingContext *c, NSMutableDictionary *offer, uint32_t status, BOOL error) {
    if ([offer[@"release_sent"] boolValue]) { fault(c, @"duplicate-native-completion"); return; }
    auto ticket = ticketFor(c, offer);
    if (c->ledger->finishConsumer(ticket, status, error) != mpc::LeaseResult::Ok) {
        fault(c, @"consumer-terminal-state"); return;
    }
    uint64_t release = 0;
    if (c->ledger->issueRelease(ticket, release) != mpc::LeaseResult::Ok) {
        fault(c, @"release-before-readers-finished"); return;
    }
    offer[@"release_sent"] = @YES;
    offer[@"terminal_status"] = @(status); offer[@"terminal_error"] = @(error);
    NSMutableDictionary *buffer = bufferFor(c, ticket.resource);
    buffer[@"release"] = @(release);
    buffer[@"texture"] = NSNull.null; // Actual GPU terminal callback retired the source reader.
    BOOL sent = reply(c, MPC_RELEASE_COMPLETED, ticket, release, error ? 5u : status);
    [c.releases addObject:@{@"serial": @(ticket.serial), @"incarnation": @(ticket.incarnation),
        @"resource_id": @(ticket.resource), @"release": @(release), @"status": @(status),
        @"has_error": @(error), @"registry_id": @(c.registry), @"wire_sent": @(sent),
        @"actual_gpu_terminal_callback": @YES, @"host_seconds": @(CACurrentMediaTime())}];
}
static void control(MPCMovingContext *c, NSDictionary *row) {
    if (![row[@"schema"] isEqual:@1] || ![row[@"run"] isEqual:c.nonce] || c.finished || c->ledger->faulted()) {
        fault(c, @"control-session-or-state"); return;
    }
    NSString *kind = row[@"type"];
    if ([kind isEqual:@"register"]) {
        uint32_t resource = [row[@"resource_id"] unsignedIntValue];
        if (c.buffers.count >= 3 || ![row[@"slot"] isEqual:@(c.buffers.count)] || bufferFor(c, resource)) {
            fault(c, @"registration-slot-or-duplicate"); return;
        }
        // Native alias/alignment must still be validated in its actual callback.
        mpc::FrameLayout layout = {resource, [row[@"width"] unsignedIntValue], [row[@"height"] unsignedIntValue],
            [row[@"format"] unsignedIntValue], [row[@"row_pitch"] unsignedIntValue],
            [row[@"incarnation"] unsignedLongLongValue], [row[@"offset"] unsignedLongLongValue],
            [row[@"backing_bytes"] unsignedLongLongValue], c.registry, c.linearAlignment};
        if (layout.incarnation != 1 || c->ledger->registerBuffer(layout) != mpc::LeaseResult::Ok) {
            fault(c, @"registration-layout"); return;
        }
        NSMutableDictionary *buffer = [row mutableCopy];
        buffer[@"last_generation"] = @0; buffer[@"last_consumed_serial"] = @0; buffer[@"serial"] = @0; buffer[@"release"] = @0;
        [c.buffers addObject:buffer];
        reply(c, MPC_RELEASE_REGISTERED, {c->session, 0, 1, resource}, 0, 0); return;
    }
    if ([kind isEqual:@"offer"]) {
        unsigned index = (unsigned)c.offers.count;
        NSMutableDictionary *buffer = bufferFor(c, [row[@"resource_id"] unsignedIntValue]);
        if (index >= MPC_MOVING_FRAMES || c.buffers.count != 3 ||
            ![row[@"serial"] isEqual:@(index + 1)] || ![row[@"incarnation"] isEqual:@1] ||
            ![row[@"phase"] isEqual:@(mpc_moving_phase(index))] ||
            ![row[@"producer_fence_completed"] isEqual:@YES] || ![row[@"external_queue_release"] isEqual:@YES] ||
            !buffer || ![buffer[@"slot"] isEqual:@(index % 3)] ||
            [row[@"producer_fence"] unsignedLongLongValue] != c.nextFence + 1 || c->ledger->consumers()) {
            fault(c, @"producer-offer-order-or-ownership"); return;
        }
        mpc::FrameTicket ticket;
        if (c->ledger->beginProducer([row[@"resource_id"] unsignedIntValue], ticket) != mpc::LeaseResult::Ok ||
            ticket.serial != index + 1 || c->ledger->finishProducer(ticket,
                [row[@"producer_fence"] unsignedLongLongValue], true) != mpc::LeaseResult::Ok) {
            fault(c, @"producer-lease-not-free"); return;
        }
        c.nextFence++;
        NSMutableDictionary *offer = [row mutableCopy];
        offer[@"native_consumed"] = @NO; offer[@"release_sent"] = @NO;
        buffer[@"serial"] = @(ticket.serial); buffer[@"release"] = @0;
        [c.offers addObject:offer]; reply(c, MPC_RELEASE_ARMED, ticket, 0, 0); return;
    }
    if ([kind isEqual:@"reacquired"]) {
        auto ticket = ticketFor(c, row);
        NSMutableDictionary *buffer = bufferFor(c, ticket.resource);
        uint64_t release = [row[@"release"] unsignedLongLongValue];
        if (c.acquires.count >= 120 || !buffer || ![row[@"serial"] isEqual:buffer[@"serial"]] ||
            ![row[@"release"] isEqual:buffer[@"release"]] || ![row[@"acquire_fence_completed"] isEqual:@YES] ||
            [row[@"acquire_fence"] unsignedLongLongValue] != c.nextFence + 1 ||
            c->ledger->acknowledgeRelease(ticket, release) != mpc::LeaseResult::Ok) {
            fault(c, @"guest-reacquisition-order-or-release"); return;
        }
        c.nextFence++; [c.acquires addObject:row];
        reply(c, MPC_RELEASE_REACQUIRED, ticket, release, 0); return;
    }
    if ([kind isEqual:@"finish"]) {
        if (![row[@"frames"] isEqual:@120] || ![row[@"buffers"] isEqual:@3] ||
            c.offers.count != 120 || c.releases.count != 120 || c.acquires.count != 120 ||
            c.errors || !c->ledger->drained() || c->ledger->faulted()) {
            fault(c, @"finish-with-live-leases"); return;
        }
        for (NSMutableDictionary *buffer in c.buffers) buffer[@"texture"] = NSNull.null;
        c.finished = YES; reply(c, MPC_RELEASE_FINISHED, {c->session, 0, 0, 0}, 0, 0); return;
    }
    fault(c, @"unknown-control");
}

static NSDictionary *consume(MPCMovingContext *c, const MPCNativeScanoutEvent *event, NSMutableDictionary *offer) {
    id<MTLTexture> texture = (__bridge id<MTLTexture>)event->texture;
    id<MTLBuffer> backing = texture.buffer;
    NSUInteger alignment = [texture.device minimumLinearTextureAlignmentForPixelFormat:MTLPixelFormatBGRA8Unorm];
    __block NSDictionary *declared;
    dispatch_sync(c.executor, ^{ declared = [bufferFor(c, event->resource_id) copy]; });
    uint64_t extent = uint64_t(event->stride) * event->height;
    if (!texture || !backing || texture.device.registryID != c.registry || texture.pixelFormat != MTLPixelFormatBGRA8Unorm ||
        texture.textureType != MTLTextureType2D || texture.width != 1280 || texture.height != 720 ||
        texture.depth != 1 || texture.sampleCount != 1 || texture.mipmapLevelCount != 1 || texture.arrayLength != 1 ||
        texture.storageMode != MTLStorageModeShared || backing.storageMode != MTLStorageModeShared ||
        texture.bufferOffset != event->offset || texture.bufferBytesPerRow != event->stride ||
        !alignment || event->offset % alignment || event->stride % alignment ||
        event->offset > backing.length || extent > backing.length - event->offset ||
        ![declared[@"row_pitch"] isEqual:@(event->stride)] || ![declared[@"offset"] isEqual:@(event->offset)] ||
        [declared[@"backing_bytes"] unsignedLongLongValue] > backing.length)
        return @{@"error": @"native-alias-layout-device"};
    const unsigned index = [offer[@"serial"] unsignedIntValue] - 1, phase = mpc_moving_phase(index);
    const BOOL endpoint = mpc_moving_endpoint(index);
    auto ticket = ticketFor(c, offer);
    NSMutableDictionary *image = [@{@"serial": @(ticket.serial), @"incarnation": @(ticket.incarnation),
        @"resource_id": @(event->resource_id), @"generation": @(event->generation), @"phase": @(phase),
        @"flush_sequence": @(event->sequence),
        @"width": @1280, @"height": @720, @"row_pitch": @(event->stride), @"offset": @(event->offset),
        @"backing_bytes": @(backing.length), @"linear_alignment": @(alignment),
        @"native_pixel_format": @(texture.pixelFormat), @"native_registry_id": @(texture.device.registryID),
        @"virtio_format": @(event->format), @"channel_order": @"bgra", @"native_buffer_alias_verified": @YES,
        @"pixel_verification_performed": @(endpoint), @"pixels_checked": @0, @"channel_sum": @0, @"mismatches": @0} mutableCopy];
    __block BOOL consumerBegun = NO;
    BOOL (^beginConsumer)(void) = ^BOOL {
        __block BOOL allowed = NO;
        dispatch_sync(c.executor, ^{
            if (consumerBegun) { allowed = !c->ledger->faulted(); return; }
            allowed = c->ledger->beginConsumer(ticket, c.registry) == mpc::LeaseResult::Ok;
            if (allowed) { consumerBegun = YES; bufferFor(c, ticket.resource)[@"texture"] = texture; }
        });
        return allowed;
    };
    if (endpoint) {
        id<MTLBuffer> readback = [texture.device newBufferWithLength:1280 * 720 * 4 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> command = [c.queue commandBuffer];
        id<MTLBlitCommandEncoder> encoder = [command blitCommandEncoder];
        if (!readback || !command || !encoder) return @{@"error": @"endpoint-allocation"};
        [encoder copyFromTexture:texture sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0)
            sourceSize:MTLSizeMake(1280, 720, 1) toBuffer:readback destinationOffset:0
            destinationBytesPerRow:5120 destinationBytesPerImage:1280 * 720 * 4];
        [encoder endEncoding];
        dispatch_semaphore_t done = dispatch_semaphore_create(0);
        // Executor-owned join handles both completion-before-timeout and a late
        // real completion. A CPU timeout never fabricates GPU retirement.
        NSMutableDictionary *join = [NSMutableDictionary dictionary];
        [command addCompletedHandler:^(id<MTLCommandBuffer> completed) {
            (void)texture; (void)readback;
            dispatch_async(c.executor, ^{
                join[@"completed"] = @YES; join[@"status"] = @(completed.status); join[@"error"] = @(completed.error != nil);
                if ([join[@"abandoned"] boolValue]) releaseConsumer(c, offer, (uint32_t)completed.status, completed.error != nil);
            });
            dispatch_semaphore_signal(done);
        }];
        if (!beginConsumer()) return @{@"error": @"endpoint-lease"};
        dispatch_sync(c.executor, ^{ c.readbacks++; });
        [command commit];
        if (dispatch_semaphore_wait(done, dispatch_time(DISPATCH_TIME_NOW, 5 * NSEC_PER_SEC))) {
            dispatch_sync(c.executor, ^{
                join[@"abandoned"] = @YES; fault(c, @"endpoint-timeout");
                if ([join[@"completed"] boolValue]) releaseConsumer(c, offer,
                    [join[@"status"] unsignedIntValue], [join[@"error"] boolValue]);
            });
            return @{@"error": @"endpoint-timeout"};
        }
        if (command.status != MTLCommandBufferStatusCompleted || command.error) {
            dispatch_sync(c.executor, ^{ releaseConsumer(c, offer, (uint32_t)command.status, command.error != nil); });
            return @{@"error": @"endpoint-command-failed"};
        }
        const unsigned char *pixels = static_cast<const unsigned char *>(readback.contents);
        uint64_t sum = 0, mismatches = 0;
        for (unsigned y = 0; y < 720; ++y) for (unsigned x = 0; x < 1280; ++x) {
            const auto *p = pixels + (y * 1280 + x) * 4;
            mismatches += !mpc_moving_pattern_matches(p, x, y, phase, 1);
            sum += p[0] + p[1] + p[2] + p[3];
        }
        image[@"pixels_checked"] = @921600; image[@"channel_sum"] = @(sum); image[@"mismatches"] = @(mismatches);
        image[@"endpoint_consumer_status"] = @(command.status); image[@"endpoint_consumer_error"] = @NO;
    }
    NSDictionary *present = MPCGuestMovingScreenConsume(event, image, beginConsumer, ^(uint32_t status, BOOL error) {
        dispatch_async(c.executor, ^{ releaseConsumer(c, offer, status, error); });
    });
    image[@"screen_submission"] = present;
    if (present[@"error"]) {
        dispatch_sync(c.executor, ^{
            fault(c, @"screen-consumer-failed");
            if (![present[@"gpu_submitted"] boolValue] && consumerBegun) {
                // Only endpoint work was submitted, and its actual completion
                // was observed above. No screen source reader ever started.
                releaseConsumer(c, offer, 4, NO);
            }
        });
        image[@"error"] = present[@"error"];
    }
    return image;
}

static void scanout(void *opaque, const MPCNativeScanoutEvent *event) {
    @autoreleasepool {
        MPCMovingContext *c = (__bridge MPCMovingContext *)opaque;
        __block NSMutableDictionary *offer = nil;
        // Borrowed texture is retained while its callback is valid, before work.
        id<MTLTexture> texture = event ? (__bridge id<MTLTexture>)event->texture : nil;
        dispatch_sync(c.executor, ^{
            if (!event || event->abi != 1 || event->bytes != sizeof(*event) || event->sequence != c.sequence + 1 || c.events.count >= 2048) {
                fault(c, @"scanout-event-order-or-abi"); return;
            }
            c.sequence = event->sequence;
            [c.events addObject:@{@"kind": @(event->kind), @"sequence": @(event->sequence),
                @"resource_id": @(event->resource_id), @"generation": @(event->generation)}];
            if (event->kind == MPC_SCANOUT_DISABLE) {
                if (!c.active || event->resource_id != c.activeResource || event->generation != c.generation) fault(c, @"disable-identity");
                c.active = NO; return;
            }
            if (c->ledger->faulted()) return;
            NSMutableDictionary *buffer = bufferFor(c, event->resource_id);
            if (!buffer || !texture || event->width != 1280 || event->height != 720 ||
                event->format != MPC_IMAGE_VIRTIO_BGRX8 || event->x || event->y ||
                event->crop_width != 1280 || event->crop_height != 720 || event->y_0_top) {
                fault(c, @"scanout-resource-layout"); return;
            }
            if (event->kind == MPC_SCANOUT_INSTALL) {
                if (c.active || event->generation <= c.generation) { fault(c, @"install-generation"); return; }
                c.active = YES; c.generation = event->generation; c.activeResource = event->resource_id; return;
            }
            if (event->kind != MPC_SCANOUT_FLUSH || !c.active || event->resource_id != c.activeResource || event->generation != c.generation) {
                fault(c, @"flush-identity"); return;
            }
            NSMutableDictionary *candidate = c.offers.lastObject;
            auto resourceTicket = ticketFor(c, buffer);
            auto state = c->ledger->state(event->resource_id);
            auto decision = mpc::classifyMovingFlush(c->session, resourceTicket, ticketFor(c, candidate),
                [buffer[@"last_consumed_serial"] unsignedLongLongValue], state);
            if (decision == mpc::MovingFlushDecision::RefreshOnly) {
                // Even a new installation generation can refresh already claimed
                // content. Preserve the event; submit no reader and issue no release.
                if ([buffer[@"last_generation"] unsignedLongLongValue] == event->generation) c.repeatedFlushes++;
                [c.refreshes addObject:@{@"event_sequence": @(event->sequence), @"generation": @(event->generation),
                    @"resource_id": @(event->resource_id), @"serial": @(resourceTicket.serial),
                    @"incarnation": @(resourceTicket.incarnation), @"lease_state": @((unsigned)state),
                    @"native_reads_added": @0, @"releases_added": @0}];
                MPCDiagnosticStage(@"linux-moving-refresh-without-new-reader", @{@"resource_id": @(event->resource_id),
                    @"serial": @(resourceTicket.serial), @"generation": @(event->generation)});
                return;
            }
            if (decision != mpc::MovingFlushDecision::Consume || c.finished || [candidate[@"native_consumed"] boolValue] ||
                event->generation <= [buffer[@"last_generation"] unsignedLongLongValue]) { fault(c, @"flush-not-armed"); return; }
            candidate[@"native_consumed"] = @YES; candidate[@"generation"] = @(event->generation);
            candidate[@"flush_sequence"] = @(event->sequence);
            buffer[@"last_generation"] = @(event->generation); buffer[@"last_consumed_serial"] = @(resourceTicket.serial); offer = candidate;
        });
        if (!offer) return;
        NSDictionary *image = consume(c, event, offer);
        dispatch_sync(c.executor, ^{
            if (c.images.count >= 120) { fault(c, @"image-overflow"); return; }
            [c.images addObject:image];
            if (image[@"error"]) fault(c, image[@"error"]);
        });
    }
}

BOOL MPCMovingTransportBegin(NSString *nonce, void *engine, NSString *serialPath, NSError **error) {
    auto configure = reinterpret_cast<MPCConfigureNativeScanout>(dlsym(engine, "mpc_qemu_configure_native_scanout"));
    uint64_t high = 0, low = 0;
    if (moving || !configure || !mpc_wire_session(nonce.UTF8String, &high, &low)) return NO;
    MPCMovingContext *c = [MPCMovingContext new]; moving = c;
    c.hostFD = c.engineFD = c.logFD = -1;
    c.nonce = nonce; c.registry = MTLCreateSystemDefaultDevice().registryID;
    c.linearAlignment = [MTLCreateSystemDefaultDevice() minimumLinearTextureAlignmentForPixelFormat:MTLPixelFormatBGRA8Unorm];
    c->session = {high, low}; c->ledger = std::make_unique<mpc::FrameLeaseLedger>(c->session, c.registry);
    c.executor = dispatch_queue_create("com.mypc.linux-moving-release", DISPATCH_QUEUE_SERIAL);
    c.queue = [MTLCreateSystemDefaultDevice() newCommandQueue];
    c.buffers = [NSMutableArray array]; c.offers = [NSMutableArray array]; c.releases = [NSMutableArray array];
    c.acquires = [NSMutableArray array]; c.images = [NSMutableArray array]; c.events = [NSMutableArray array]; c.refreshes = [NSMutableArray array];
    int pair[2];
    if (!c.registry || !c.queue || socketpair(AF_UNIX, SOCK_STREAM, 0, pair)) goto failed;
    c.hostFD = pair[0]; c.engineFD = pair[1];
    { int one = 1; struct timeval timeout = {1, 0};
      if (setsockopt(c.hostFD, SOL_SOCKET, SO_NOSIGPIPE, &one, sizeof(one)) ||
          setsockopt(c.hostFD, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout))) goto failed; }
    c.logFD = open(serialPath.fileSystemRepresentation, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (c.logFD < 0 || configure(1, sizeof(MPCNativeScanoutEvent), scanout, (__bridge void *)c) != 1) goto failed;
    c->readerExited.store(false);
    c->reader = std::thread([c] {
        @autoreleasepool {
            std::string pending; size_t total = 0; char bytes[8192]; BOOL eof = NO;
            while (true) {
                ssize_t n = read(c.hostFD, bytes, sizeof(bytes));
                if (n < 0 && errno == EINTR) continue;
                if (n <= 0) { eof = n == 0; break; }
                total += (size_t)n;
                if (total > 8u * 1024u * 1024u || !writeAll(c.logFD, bytes, (size_t)n, NO)) {
                    dispatch_sync(c.executor, ^{ fault(c, @"serial-log-bounds-or-write"); }); break;
                }
                pending.append(bytes, (size_t)n);
                if (pending.size() > 65536) { dispatch_sync(c.executor, ^{ fault(c, @"serial-line-bounds"); }); break; }
                size_t end;
                while ((end = pending.find('\n')) != std::string::npos) {
                    std::string line = pending.substr(0, end); pending.erase(0, end + 1);
                    while (!line.empty() && line.back() == '\r') line.pop_back();
                    if (line.rfind("MPC_MOVE_CTL ", 0) != 0) continue;
                    if (line.size() > 4096) { dispatch_sync(c.executor, ^{ fault(c, @"control-line-bounds"); }); continue; }
                    NSData *data = [NSData dataWithBytes:line.data() + 13 length:line.size() - 13];
                    id row = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
                    dispatch_sync(c.executor, ^{
                        if ([row isKindOfClass:NSDictionary.class]) control(c, row);
                        else fault(c, @"control-json");
                    });
                }
            }
            fsync(c.logFD); close(c.logFD); c.logFD = -1;
            dispatch_sync(c.executor, ^{ c.channelEOF = eof; if (!eof) fault(c, @"channel-read-termination"); });
        }
        c->readerExited.store(true);
    });
    MPCDiagnosticStage(@"linux-moving-channel-configured", @{@"buffers": @3, @"frames": @120,
        @"transport": @"local-socketpair-linux-uart-explicit-diagnostic", @"production_kms_wsi": @NO});
    return YES;
failed:
    if (c.hostFD >= 0) { close(c.hostFD); c.hostFD = -1; }
    if (c.engineFD >= 0) { close(c.engineFD); c.engineFD = -1; }
    if (c.logFD >= 0) { close(c.logFD); c.logFD = -1; }
    if (error) *error = [NSError errorWithDomain:@"MovingTransport" code:1 userInfo:@{
        NSLocalizedDescriptionKey: @"Could not prepare the private Linux release channel."}];
    return NO;
}
int MPCMovingTransportEngineFD(void) { return moving ? moving.engineFD : -1; }
void MPCMovingTransportTransferEngineFD(void) {
    // QEMU socket_connect(fd:) adopts the numeric descriptor; its QIO channel
    // finalizer closes it. Never close the transferred integer a second time.
    if (moving) moving.transferred = YES;
}
void MPCMovingTransportJoinReader(BOOL engineFinished) {
    if (!moving || !engineFinished) return;
    MPCMovingContext *c = moving;
    for (unsigned i = 0; i < 200 && !c->readerExited.load(); ++i) usleep(10000);
    if (!c->readerExited.load()) {
        shutdown(c.hostFD, SHUT_RDWR);
        dispatch_sync(c.executor, ^{ fault(c, @"reader-eof-not-observed-after-engine-cleanup"); });
    }
    if (c->reader.joinable()) c->reader.join();
    c.readerJoined = YES;
    close(c.hostFD); c.hostFD = -1;
    if (!c.transferred && c.engineFD >= 0) close(c.engineFD);
    c.engineFD = -1;
}
NSDictionary *MPCMovingTransportFinish(NSString *serial, BOOL engineFinished, BOOL linuxPassed, BOOL metalPassed) {
    if (!moving) return @{@"buffer_reuse_verified": @NO, @"reason": @"moving-adapter-not-created"};
    MPCMovingContext *c = moving;
    __block NSDictionary *native;
    dispatch_sync(c.executor, ^{
        NSMutableArray *buffers = [NSMutableArray array], *offers = [NSMutableArray array], *images = [NSMutableArray array];
        for (NSDictionary *row in c.buffers) { NSMutableDictionary *copy = [row mutableCopy]; [copy removeObjectForKey:@"texture"]; [buffers addObject:copy]; }
        for (NSDictionary *row in c.offers) [offers addObject:[row copy]];
        for (NSDictionary *row in c.images) [images addObject:[row copy]];
        native = @{@"schema": @1, @"scope": @"native-explicit-linux-moving-release", @"run": c.nonce,
            @"registry_id": @(c.registry), @"buffers": buffers, @"offers": offers, @"releases": [c.releases copy],
            @"reacquisitions": [c.acquires copy], @"images": images, @"events": [c.events copy],
            @"refreshes": [c.refreshes copy], @"refresh_flushes_skipped": @(c.refreshes.count), @"refresh_contract": @1,
            @"errors": @(c.errors), @"finished": @(c.finished), @"active": @(c.active),
            @"ledger_drained": @(c->ledger->drained()), @"ledger_faulted": @(c->ledger->faulted()),
            @"pending_consumers": @(c->ledger->consumers()), @"reader_joined": @(c.readerJoined),
            @"channel_eof": @(c.channelEOF), @"diagnostic_full_image_readbacks": @(c.readbacks),
            @"repeated_flushes_skipped": @(c.repeatedFlushes), @"binary_replies_sent": @(c.replies),
            @"final_submission_fence": @(c.nextFence), @"source_release": @"actual-metal-gpu-terminal-callback",
            @"production_kms_wsi_verified": @NO};
    });
    return MPCValidateMovingFrames(serial, c.nonce, native, MPCGuestMovingScreenSnapshot(), engineFinished, linuxPassed, metalPassed);
}
