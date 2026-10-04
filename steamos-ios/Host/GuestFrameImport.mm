#import "GuestFrameImport.h"
#import "ProbeBridge.h"
#import "GuestScreenPresentation.h"
#import <Metal/Metal.h>
#include "../Engine/NativeScanoutABI.h"
#include "../Engine/FrameSequenceContract.h"
#include "GuestFrameBudget.h"
#include <dlfcn.h>
#include <cmath>

@interface MPCFrameImportContext : NSObject {
@public
    MPCFrameBudget readbackBudget;
}
@property(nonatomic, copy) NSString *nonce;
@property(nonatomic, strong) id<MTLCommandQueue> queue;
@property(nonatomic, strong) NSMutableArray *events;
@property(nonatomic, strong) NSMutableArray *images;
@property(nonatomic) uint64_t sequence, generation, resource, registry;
@property(nonatomic) NSUInteger errors, skippedFlushes, readbacks;
@property(nonatomic) BOOL active, reading;
@property(nonatomic) BOOL presentToScreen;
@end
@implementation MPCFrameImportContext
@end
static MPCFrameImportContext *frameContext;

static NSDictionary *consume(MPCFrameImportContext *context, const MPCNativeScanoutEvent *event) {
    @autoreleasepool {
        MPCDiagnosticStage(@"linux-native-import-entering-consumer", @{
            @"resource_id": @(event->resource_id), @"generation": @(event->generation),
            @"width": @(event->width), @"height": @(event->height),
            @"row_pitch": @(event->stride), @"offset": @(event->offset)});
        // ARC retains the borrowed handle before any consumer GPU work starts.
        id<MTLTexture> texture = (__bridge id<MTLTexture>)event->texture;
        if (!texture) return @{@"error": @"missing-native-texture"};
        id<MTLDevice> device = texture.device;
        NSUInteger alignment = [device minimumLinearTextureAlignmentForPixelFormat:MTLPixelFormatBGRA8Unorm];
        id<MTLBuffer> backing = texture.buffer;
        uint64_t extent = (uint64_t)event->stride * event->height;
        if (!device || device.registryID != context.registry || !backing ||
            texture.pixelFormat != MTLPixelFormatBGRA8Unorm || texture.textureType != MTLTextureType2D ||
            texture.width != 1280 || texture.height != 720 || texture.depth != 1 || texture.sampleCount != 1 ||
            texture.mipmapLevelCount != 1 || texture.arrayLength != 1 ||
            texture.storageMode != MTLStorageModeShared || backing.storageMode != MTLStorageModeShared ||
            texture.bufferOffset != event->offset || texture.bufferBytesPerRow != event->stride ||
            !alignment || event->offset % alignment || event->stride % alignment ||
            event->offset > backing.length || extent > backing.length - event->offset)
            return @{@"error": @"native-linear-image-device-format-layout-bounds"};
        if (!context.queue) context.queue = [device newCommandQueue];
        unsigned index = context.images.count;
        unsigned phase = mpc_frame_phase(index);
        BOOL endpoint = index == 0 || index == 7;
        NSMutableDictionary *layout = [@{@"resource_id": @(event->resource_id), @"generation": @(event->generation),
            @"phase": @(phase), @"width": @1280, @"height": @720, @"row_pitch": @(event->stride),
            @"offset": @(event->offset), @"backing_bytes": @(backing.length), @"linear_alignment": @(alignment),
            @"native_pixel_format": @(texture.pixelFormat), @"native_registry_id": @(device.registryID),
            @"virtio_format": @(event->format), @"channel_order": @"bgra", @"native_buffer_alias_verified": @YES,
            @"pixel_verification_performed": @(endpoint), @"pixels_checked": @0, @"channel_sum": @0,
            @"mismatches": @0, @"native_device": device.name ?: @"unknown"} mutableCopy];
        if (!endpoint) return layout;
        id<MTLBuffer> readback = [device newBufferWithLength:1280 * 720 * 4 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> command = [context.queue commandBuffer];
        id<MTLBlitCommandEncoder> encoder = [command blitCommandEncoder];
        if (!context.queue || !readback || !command || !encoder) return @{@"error": @"native-consumer-allocation"};
        [encoder copyFromTexture:texture sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0)
                      sourceSize:MTLSizeMake(1280, 720, 1) toBuffer:readback destinationOffset:0
             destinationBytesPerRow:1280 * 4 destinationBytesPerImage:1280 * 720 * 4];
        [encoder endEncoding];
        dispatch_semaphore_t semaphore = dispatch_semaphore_create(0);
        [command addCompletedHandler:^(id<MTLCommandBuffer> completed) {
            // Keep the borrowed texture/backing alive even if the wait times out.
            (void)texture; (void)readback;
            dispatch_semaphore_signal(semaphore);
        }];
        MPCDiagnosticStage(@"linux-native-import-before-consumer", @{@"resource_id": @(event->resource_id),
            @"generation": @(event->generation), @"row_pitch": @(event->stride), @"offset": @(event->offset)});
        context.readbacks++;
        [command commit];
        if (dispatch_semaphore_wait(semaphore, dispatch_time(DISPATCH_TIME_NOW, 5 * NSEC_PER_SEC)))
            return @{@"error": @"native-consumer-timeout"};
        if (command.status != MTLCommandBufferStatusCompleted || command.error)
            return @{@"error": @"native-consumer-command-failed", @"status": @(command.status),
                     @"code": @(command.error.code)};
        const auto *pixels = static_cast<const unsigned char *>(readback.contents);
        // Check the expected endpoint phase, not an inferred/host-produced substitute.
        uint64_t mismatches = 0, sum = 0;
        for (unsigned y = 0; y < 720; ++y) for (unsigned x = 0; x < 1280; ++x) {
            const unsigned char *p = pixels + (y * 1280 + x) * 4;
            mismatches += !mpc_frame_pattern_matches(p, x, y, phase, 1);
            sum += p[0] + p[1] + p[2] + p[3];
        }
        MPCDiagnosticStage(@"linux-native-import-consumer-completed", @{@"phase": @(phase), @"mismatches": @(mismatches)});
        return @{@"resource_id": @(event->resource_id), @"generation": @(event->generation), @"phase": @(phase),
            @"width": @1280, @"height": @720, @"row_pitch": @(event->stride), @"offset": @(event->offset),
            @"backing_bytes": @(backing.length), @"linear_alignment": @(alignment),
            @"native_pixel_format": @(texture.pixelFormat), @"native_registry_id": @(device.registryID),
            @"channel_order": @"bgra", @"virtio_format": @(event->format),
            @"native_device": device.name ?: @"unknown", @"native_buffer_alias_verified": @YES,
            @"pixel_verification_performed": @YES, @"pixels_checked": @921600, @"mismatches": @(mismatches), @"channel_sum": @(sum),
            @"consumer_status": @(command.status), @"consumer_error": @NO,
            @"gpu_start_seconds": @(command.GPUStartTime), @"gpu_end_seconds": @(command.GPUEndTime)};
    }
}

static void scanout(void *opaque, const MPCNativeScanoutEvent *event) {
    @autoreleasepool {
        MPCFrameImportContext *context = (__bridge MPCFrameImportContext *)opaque;
        @synchronized(context) {
            if (!event || event->abi != 1 || event->bytes != sizeof(*event) ||
                event->sequence != context.sequence + 1 || context.events.count >= 64) { context.errors++; return; }
            context.sequence = event->sequence;
            [context.events addObject:@{@"kind": @(event->kind), @"sequence": @(event->sequence),
                @"generation": @(event->generation), @"resource_id": @(event->resource_id)}];
            if (event->kind == MPC_SCANOUT_DISABLE) {
                if (!context.active || event->generation != context.generation || event->resource_id != context.resource)
                    context.errors++;
                context.active = NO;
                return;
            }
            if (!event->texture || !event->resource_id || event->width != 1280 || event->height != 720 ||
                event->format != MPC_IMAGE_VIRTIO_BGRX8 || event->stride < 5120 || event->stride > (1u << 24) ||
                event->x || event->y || event->crop_width != 1280 || event->crop_height != 720 ||
                event->y_0_top) { context.errors++; return; }
            if (event->kind == MPC_SCANOUT_INSTALL) {
                if (context.active || event->generation <= context.generation) { context.errors++; return; }
                context.generation = event->generation;
                context.resource = event->resource_id;
                context.active = YES;
                MPCDiagnosticStage(@"linux-native-image-installed", @{
                    @"resource_id": @(event->resource_id), @"generation": @(event->generation)});
                return;
            }
            if (event->kind != MPC_SCANOUT_FLUSH || !context.active || event->generation != context.generation ||
                event->resource_id != context.resource || context.reading) { context.errors++; return; }
            int decision = mpc_reserve_frame(&context->readbackBudget, event);
            if (decision == MPC_FRAME_BUDGET_REPEAT) { context.skippedFlushes++; return; }
            if (decision != MPC_FRAME_BUDGET_CONSUME) { context.errors++; return; }
            context.reading = YES;
        }
        NSDictionary *row = consume(context, event);
        if (row[@"error"]) MPCDiagnosticStage(@"linux-native-import-consumer-rejected", row);
        if (context.presentToScreen && !row[@"error"]) {
            // Screen submission uses this exact borrowed/retained guest texture,
            // never the diagnostic readback buffer or a native generated image.
            MPCGuestScreenConsume(event, row);
        }
        @synchronized(context) {
            [context.images addObject:row];
            if (row[@"error"]) context.errors++;
            context.reading = NO;
        }
    }
}

BOOL MPCGuestFrameImportBegin(NSString *nonce, void *engine, NSError **error) {
    auto configure = reinterpret_cast<MPCConfigureNativeScanout>(dlsym(engine, "mpc_qemu_configure_native_scanout"));
    if (!configure || frameContext) {
        if (error) *error = [NSError errorWithDomain:@"GuestFrameImport" code:1
            userInfo:@{NSLocalizedDescriptionKey: @"Native image adapter unavailable or already configured."}];
        return NO;
    }
    frameContext = [MPCFrameImportContext new];
    frameContext.nonce = nonce;
    frameContext.presentToScreen = YES;
    frameContext.events = [NSMutableArray array];
    frameContext.images = [NSMutableArray array];
    frameContext.registry = MTLCreateSystemDefaultDevice().registryID;
    // The engine/context stay loaded for process lifetime, including timeout recovery.
    if (!frameContext.registry || configure(1, sizeof(MPCNativeScanoutEvent), scanout, (__bridge void *)frameContext) != 1) {
        if (error) *error = [NSError errorWithDomain:@"GuestFrameImport" code:2
            userInfo:@{NSLocalizedDescriptionKey: @"Native image adapter ABI/device preflight failed."}];
        return NO;
    }
    return YES;
}

NSDictionary *MPCGuestFrameImportFinish(NSString *serial, BOOL engineFinished, BOOL linuxPassed, BOOL guestMetalPassed) {
    if (!frameContext) return @{@"host_memory_import_verified": @NO, @"reason": @"image-adapter-not-configured"};
    NSDictionary *native;
    @synchronized(frameContext) {
        native = @{@"scope": @"native-metal-linux-eight-frame-import", @"run": frameContext.nonce,
            @"events": [frameContext.events copy], @"images": [frameContext.images copy],
            @"errors": @(frameContext.errors), @"active": @(frameContext.active), @"reading": @(frameContext.reading),
            @"skipped_repeat_flushes": @(frameContext.skippedFlushes), @"registry_id": @(frameContext.registry),
            @"diagnostic_full_image_readbacks": @(frameContext.readbacks),
            @"presentation_verified": @NO, @"zero_copy_transport_verified": @NO};
    }
    return MPCValidateGuestFrameImport(serial, frameContext.nonce, native, engineFinished, linuxPassed, guestMetalPassed);
}
