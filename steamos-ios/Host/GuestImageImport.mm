#import "GuestImageImport.h"
#import "ProbeBridge.h"
#import <Metal/Metal.h>
#include "../Engine/NativeScanoutABI.h"
#include <dlfcn.h>
#include <cmath>

@interface MPCImageImportContext : NSObject
@property(nonatomic, copy) NSString *nonce;
@property(nonatomic, strong) id<MTLCommandQueue> queue;
@property(nonatomic, strong) NSMutableArray *events;
@property(nonatomic, strong) NSMutableArray *images;
@property(nonatomic, strong) NSMutableSet *consumed;
@property(nonatomic) uint64_t sequence, generation, resource, registry;
@property(nonatomic) NSUInteger errors, skippedFlushes;
@property(nonatomic) BOOL active, reading;
@end
@implementation MPCImageImportContext
@end
static MPCImageImportContext *imageContext;

static NSDictionary *consume(MPCImageImportContext *context, const MPCNativeScanoutEvent *event) {
    @autoreleasepool {
        // ARC retains the borrowed handle before any consumer GPU work starts.
        id<MTLTexture> texture = (__bridge id<MTLTexture>)event->texture;
        if (!texture) return @{@"error": @"missing-native-texture"};
        id<MTLDevice> device = texture.device;
        NSUInteger alignment = [device minimumLinearTextureAlignmentForPixelFormat:MTLPixelFormatRGBA8Unorm];
        id<MTLBuffer> backing = texture.buffer;
        uint64_t extent = (uint64_t)event->stride * event->height;
        if (!device || device.registryID != context.registry || !backing ||
            texture.pixelFormat != MTLPixelFormatRGBA8Unorm || texture.textureType != MTLTextureType2D ||
            texture.width != 1280 || texture.height != 720 || texture.depth != 1 || texture.sampleCount != 1 ||
            texture.mipmapLevelCount != 1 || texture.arrayLength != 1 ||
            texture.storageMode != MTLStorageModeShared || backing.storageMode != MTLStorageModeShared ||
            texture.bufferOffset != event->offset || texture.bufferBytesPerRow != event->stride ||
            !alignment || event->offset % alignment || event->stride % alignment ||
            event->offset > backing.length || extent > backing.length - event->offset)
            return @{@"error": @"native-linear-image-device-format-layout-bounds"};
        if (!context.queue) context.queue = [device newCommandQueue];
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
        [command commit];
        if (dispatch_semaphore_wait(semaphore, dispatch_time(DISPATCH_TIME_NOW, 5 * NSEC_PER_SEC)))
            return @{@"error": @"native-consumer-timeout"};
        if (command.status != MTLCommandBufferStatusCompleted || command.error)
            return @{@"error": @"native-consumer-command-failed", @"status": @(command.status),
                     @"code": @(command.error.code)};
        const auto *pixels = static_cast<const unsigned char *>(readback.contents);
        unsigned phase = pixels[2] == 165 ? 0 : pixels[2] == (165 ^ 41) ? 41 : 999;
        uint64_t mismatches = 0, sum = 0;
        for (unsigned y = 0; y < 720; ++y) for (unsigned x = 0; x < 1280; ++x) {
            const unsigned char *p = pixels + (y * 1280 + x) * 4;
            mismatches += phase == 999 || p[0] != ((x + phase) & 255) || p[1] != ((y + phase) & 255) ||
                          p[2] != ((165 ^ phase) & 255) || p[3] != 255;
            sum += p[0] + p[1] + p[2] + p[3];
        }
        MPCDiagnosticStage(@"linux-native-import-consumer-completed", @{@"phase": @(phase), @"mismatches": @(mismatches)});
        return @{@"resource_id": @(event->resource_id), @"generation": @(event->generation), @"phase": @(phase),
            @"width": @1280, @"height": @720, @"row_pitch": @(event->stride), @"offset": @(event->offset),
            @"backing_bytes": @(backing.length), @"linear_alignment": @(alignment),
            @"native_pixel_format": @(texture.pixelFormat), @"native_registry_id": @(device.registryID),
            @"native_device": device.name ?: @"unknown", @"native_buffer_alias_verified": @YES,
            @"pixels_checked": @921600, @"mismatches": @(mismatches), @"channel_sum": @(sum),
            @"consumer_status": @(command.status), @"consumer_error": @NO,
            @"gpu_start_seconds": @(command.GPUStartTime), @"gpu_end_seconds": @(command.GPUEndTime)};
    }
}

static void scanout(void *opaque, const MPCNativeScanoutEvent *event) {
    @autoreleasepool {
        MPCImageImportContext *context = (__bridge MPCImageImportContext *)opaque;
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
                event->format != 67 || event->stride < 5120 || event->stride > (1u << 24) ||
                event->x || event->y || event->crop_width != 1280 || event->crop_height != 720 ||
                event->y_0_top) { context.errors++; return; }
            if (event->kind == MPC_SCANOUT_INSTALL) {
                if (context.active || event->generation <= context.generation) { context.errors++; return; }
                context.generation = event->generation;
                context.resource = event->resource_id;
                context.active = YES;
                return;
            }
            if (event->kind != MPC_SCANOUT_FLUSH || !context.active || event->generation != context.generation ||
                event->resource_id != context.resource || context.reading) { context.errors++; return; }
            if ([context.consumed containsObject:@(event->generation)]) { context.skippedFlushes++; return; }
            if (context.images.count >= 2) { context.errors++; return; }
            [context.consumed addObject:@(event->generation)];
            context.reading = YES;
        }
        NSDictionary *row = consume(context, event);
        @synchronized(context) {
            [context.images addObject:row];
            if (row[@"error"]) context.errors++;
            context.reading = NO;
        }
    }
}

BOOL MPCGuestImageImportBegin(NSString *nonce, void *engine, NSError **error) {
    auto configure = reinterpret_cast<MPCConfigureNativeScanout>(dlsym(engine, "mpc_qemu_configure_native_scanout"));
    if (!configure || imageContext) {
        if (error) *error = [NSError errorWithDomain:@"GuestImageImport" code:1
            userInfo:@{NSLocalizedDescriptionKey: @"Native image adapter unavailable or already configured."}];
        return NO;
    }
    imageContext = [MPCImageImportContext new];
    imageContext.nonce = nonce;
    imageContext.events = [NSMutableArray array];
    imageContext.images = [NSMutableArray array];
    imageContext.consumed = [NSMutableSet set];
    imageContext.registry = MTLCreateSystemDefaultDevice().registryID;
    // The engine/context stay loaded for process lifetime, including timeout recovery.
    if (!imageContext.registry || configure(1, sizeof(MPCNativeScanoutEvent), scanout, (__bridge void *)imageContext) != 1) {
        if (error) *error = [NSError errorWithDomain:@"GuestImageImport" code:2
            userInfo:@{NSLocalizedDescriptionKey: @"Native image adapter ABI/device preflight failed."}];
        return NO;
    }
    return YES;
}

NSDictionary *MPCGuestImageImportFinish(NSString *serial, BOOL engineFinished, BOOL linuxPassed, BOOL guestMetalPassed) {
    if (!imageContext) return @{@"host_memory_import_verified": @NO, @"reason": @"image-adapter-not-configured"};
    NSDictionary *native;
    @synchronized(imageContext) {
        native = @{@"scope": @"native-metal-linux-linear-image-import", @"run": imageContext.nonce,
            @"events": [imageContext.events copy], @"images": [imageContext.images copy],
            @"errors": @(imageContext.errors), @"active": @(imageContext.active), @"reading": @(imageContext.reading),
            @"skipped_repeat_flushes": @(imageContext.skippedFlushes), @"registry_id": @(imageContext.registry),
            @"diagnostic_full_image_readbacks": @(imageContext.images.count),
            @"presentation_verified": @NO, @"zero_copy_transport_verified": @NO};
    }
    return MPCValidateGuestImageImport(serial, imageContext.nonce, native, engineFinished, linuxPassed, guestMetalPassed);
}
