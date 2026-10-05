// Fresh, bounded two-image screen diagnostic, MIT. No host-generated image.
#import "GuestScreenPresentation.h"
#import "ProbeBridge.h"
#import "GuestFrameImport.h"
#import <UIKit/UIKit.h>
#import <QuartzCore/CAMetalLayer.h>
#import <Metal/Metal.h>
#include <cmath>
#include "../Engine/MovingFrameContract.h"

@interface MPCScreenContext : NSObject
@property(nonatomic, strong) CAMetalLayer *layer;
@property(nonatomic, strong) id<MTLCommandQueue> queue;
@property(nonatomic, strong) id<MTLRenderPipelineState> pipeline;
@property(nonatomic, strong) NSMutableArray *frames;
@property(nonatomic, strong) NSMutableArray *lifecycle;
@property(nonatomic, copy) NSString *nonce;
@property(nonatomic, strong) dispatch_queue_t renderQueue;
@property(nonatomic) uint64_t registry, geometry;
@property(nonatomic) NSUInteger errors, pending;
@property(nonatomic) BOOL visible, begun, interrupted, finished, frameSequence;
@property(nonatomic) BOOL movingSequence;
@end
@implementation MPCScreenContext
@end
static MPCScreenContext *screen;

// Caller holds the context lock. GPU completion must precede retirement even
// when the main-thread presentation has been cancelled. Signal exactly once.
static void retire(MPCScreenContext *context, NSMutableDictionary *row, dispatch_semaphore_t done) {
    if (![row[@"completion_join_retired"] boolValue] && [row[@"gpu_completed"] boolValue] &&
        ([row[@"drawable_presented"] boolValue] || [row[@"presentation_aborted"] boolValue])) {
        row[@"completion_join_retired"] = @YES;
        context.pending--;
        dispatch_semaphore_signal(done);
    }
}
static void lifecycle(NSString *reason, BOOL interrupts) {
    NSCAssert(NSThread.isMainThread, @"Observe screen lifecycle on the main thread");
    NSDictionary *event;
    @synchronized(screen) {
        if (!screen.begun || screen.finished) return;
        if (interrupts) screen.interrupted = YES;
        event = @{@"reason": reason, @"host_seconds": @(CACurrentMediaTime()),
            @"application_state": @(UIApplication.sharedApplication.applicationState),
            @"geometry": @(screen.geometry), @"surface_visible": @(screen.visible),
            @"interrupts_acceptance": @(interrupts)};
        if (screen.lifecycle.count < 32) [screen.lifecycle addObject:event];
        else { screen.errors++; screen.interrupted = YES; }
    }
    MPCDiagnosticStage(@"linux-screen-lifecycle", event);
}

@interface MPCGuestScreenView : UIView
@end
@implementation MPCGuestScreenView
+ (Class)layerClass { return CAMetalLayer.class; }
- (void)layoutSubviews {
    [super layoutSubviews];
    CGFloat scale = self.window.screen.scale ?: UIScreen.mainScreen.scale;
    CGSize size = CGSizeMake(floor(self.bounds.size.width * scale), floor(self.bounds.size.height * scale));
    BOOL changed = NO;
    @synchronized(screen) {
        if (!CGSizeEqualToSize(size, screen.layer.drawableSize)) {
            screen.geometry++;
            changed = YES;
            screen.layer.contentsScale = scale;
            screen.layer.drawableSize = size;
        }
        screen.visible = self.window != nil && !self.hidden && size.width > 0 && size.height > 0;
    }
    if (changed) lifecycle(@"drawable-size-changed", YES);
}
- (void)didMoveToWindow {
    [super didMoveToWindow];
    @synchronized(screen) {
        screen.visible = self.window != nil;
    }
    if (!self.window) lifecycle(@"surface-left-window", YES);
    [self setNeedsLayout];
}
@end
static MPCGuestScreenView *diagnosticView;

UIView *MPCGuestScreenCreateView(void) {
    NSCAssert(NSThread.isMainThread, @"Create the screen surface on the main thread");
    if (diagnosticView) return diagnosticView;
    MPCGuestScreenView *view = [[MPCGuestScreenView alloc] initWithFrame:CGRectZero];
    diagnosticView = view;
    view.backgroundColor = UIColor.blackColor;
    screen = [MPCScreenContext new];
    screen.frames = [NSMutableArray array];
    screen.lifecycle = [NSMutableArray array];
    screen.layer = (CAMetalLayer *)view.layer;
    screen.layer.device = MTLCreateSystemDefaultDevice();
    screen.layer.pixelFormat = MTLPixelFormatBGRA8Unorm;
    screen.layer.framebufferOnly = YES;
    screen.layer.maximumDrawableCount = 2;
    screen.layer.allowsNextDrawableTimeout = YES;
    screen.layer.opaque = YES;
    // This surface has SwiftUI/UIKit controls over it. Use Apple's documented
    // Core Animation transaction route and present on the main thread only
    // after the command buffer's scheduling callback. No GPU wait on main.
    screen.layer.presentsWithTransaction = YES;
    screen.registry = screen.layer.device.registryID;
    screen.queue = [screen.layer.device newCommandQueue];
    screen.renderQueue = dispatch_queue_create("com.mypc.linux-screen", DISPATCH_QUEUE_SERIAL);
    // Metal reads the imported guest texture. This shader does not make a pattern.
    NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
        "struct V { float4 p [[position]]; float2 uv; };\n"
        "vertex V screenVertex(uint i [[vertex_id]]) {\n"
        "float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};\n"
        "V o; o.p=float4(p[i],0,1); o.uv=float2((p[i].x+1)*.5,(1-p[i].y)*.5); return o; }\n"
        "fragment float4 screenFragment(V v [[stage_in]], texture2d<float> t [[texture(0)]]) {\n"
        "constexpr sampler s(coord::normalized,address::clamp_to_edge,filter::nearest);\n"
        "return t.sample(s,v.uv); }\n";
    NSError *error = nil;
    id<MTLLibrary> library = [screen.layer.device newLibraryWithSource:source options:nil error:&error];
    MTLRenderPipelineDescriptor *descriptor = [MTLRenderPipelineDescriptor new];
    descriptor.vertexFunction = [library newFunctionWithName:@"screenVertex"];
    descriptor.fragmentFunction = [library newFunctionWithName:@"screenFragment"];
    descriptor.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    if (library) screen.pipeline = [screen.layer.device newRenderPipelineStateWithDescriptor:descriptor error:&error];
    if (!screen.pipeline || !screen.queue || !screen.registry) screen.errors++;
    for (NSString *name in @[UIApplicationWillResignActiveNotification, UIApplicationDidEnterBackgroundNotification,
                            UIApplicationDidBecomeActiveNotification, UIApplicationUserDidTakeScreenshotNotification]) {
        [NSNotificationCenter.defaultCenter addObserverForName:name object:nil
            queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *notification) {
                BOOL interrupts = [notification.name isEqual:UIApplicationWillResignActiveNotification] ||
                                  [notification.name isEqual:UIApplicationDidEnterBackgroundNotification];
                lifecycle(notification.name, interrupts);
            }];
    }
    return view;
}

static BOOL beginScreen(NSString *nonce, BOOL frames, BOOL moving, NSError **error) {
    __block BOOL active = NO;
    void (^readState)(void) = ^{ active = UIApplication.sharedApplication.applicationState == UIApplicationStateActive; };
    if (NSThread.isMainThread) readState(); else dispatch_sync(dispatch_get_main_queue(), readState);
    @synchronized(screen) {
        if (!screen || screen.begun || !active || !screen.visible || screen.errors || !screen.pipeline ||
            screen.layer.drawableSize.width <= 0 || screen.layer.drawableSize.height <= 0) {
            if (error) *error = [NSError errorWithDomain:@"GuestScreen" code:1 userInfo:@{
                NSLocalizedDescriptionKey: @"The visible Metal surface is not ready, or the session was already started."}];
            return NO;
        }
        screen.nonce = nonce;
        screen.frameSequence = frames;
        screen.movingSequence = moving;
        screen.begun = YES;
        MPCDiagnosticStage(@"linux-screen-surface-ready", @{@"registry_id": @(screen.registry),
            @"drawable_width": @(screen.layer.drawableSize.width), @"drawable_height": @(screen.layer.drawableSize.height),
            @"presentation_route": @"scheduled-main-thread-core-animation-transaction",
            @"presents_with_transaction": @(screen.layer.presentsWithTransaction)});
        return YES;
    }
}

BOOL MPCGuestScreenBegin(NSString *nonce, NSError **error) { return beginScreen(nonce, NO, NO, error); }
BOOL MPCGuestFrameScreenBegin(NSString *nonce, NSError **error) { return beginScreen(nonce, YES, NO, error); }
BOOL MPCGuestMovingScreenBegin(NSString *nonce, NSError **error) { return beginScreen(nonce, YES, YES, error); }

static NSDictionary *consumeScreen(const MPCNativeScanoutEvent *event, NSDictionary *image,
    BOOL (^willSubmit)(void), void (^completedSource)(uint32_t, BOOL)) {
    MPCScreenContext *context = screen;
    // Retain while the borrowed handle is valid. Both completion blocks retain it
    // even after a timeout, scanout disable or guest resource destruction.
    id<MTLTexture> texture = (__bridge id<MTLTexture>)event->texture;
    uint64_t resource = event->resource_id, generation = event->generation;
    NSUInteger phase = [image[@"phase"] unsignedIntegerValue];
    @synchronized(context) {
        unsigned index = (unsigned)context.frames.count;
        BOOL endpoint = context.movingSequence ? mpc_moving_endpoint(index) : !context.frameSequence || index == 0 || index == 7;
        unsigned expectedPhase = context.movingSequence ? mpc_moving_phase(index) : context.frameSequence ? index * 17u : index ? 41u : 0u;
        if (!context || !context.begun || !context.visible || context.interrupted || context.pending ||
            context.frames.count >= (context.movingSequence ? MPC_MOVING_FRAMES : context.frameSequence ? 8u : 2u) || !texture || texture.device.registryID != context.registry ||
            ![image[@"resource_id"] isEqual:@(resource)] || ![image[@"generation"] isEqual:@(generation)] ||
            ![image[@"mismatches"] isEqual:@0] || ![image[@"pixels_checked"] isEqual:(endpoint ? @921600 : @0)] ||
            (context.frameSequence && ![image[@"pixel_verification_performed"] isEqual:@(endpoint)]) || phase != expectedPhase) {
            context.errors++;
            MPCDiagnosticStage(@"linux-screen-source-rejected", @{@"resource_id": @(resource),
                @"generation": @(generation), @"phase": @(phase), @"interrupted": @(context.interrupted),
                @"surface_visible": @(context.visible), @"pending": @(context.pending)});
            return @{@"error": @"screen-source-or-surface-rejected"};
        }
        context.pending++;
    }
    dispatch_semaphore_t done = dispatch_semaphore_create(0);
    NSMutableDictionary *row = [@{@"resource_id": @(resource), @"generation": @(generation), @"phase": @(phase),
        @"source_registry_id": @(texture.device.registryID), @"source_width": @(texture.width),
        @"source_height": @(texture.height), @"source_pixel_format": @(texture.pixelFormat),
        @"source_is_imported_guest_texture": @YES, @"gpu_completed": @NO, @"drawable_presented": @NO} mutableCopy];
    @synchronized(context) { row[@"frame_index"] = @(context.frames.count + 1); [context.frames addObject:row]; }
    dispatch_async(context.renderQueue, ^{
        @autoreleasepool {
            uint64_t geometry;
            @synchronized(context) {
                geometry = context.geometry;
                if (!context.visible || context.interrupted) {
                    row[@"error"] = @"screen-surface-interrupted";
                    context.errors++; context.pending--; dispatch_semaphore_signal(done); return;
                }
            }
            id<CAMetalDrawable> drawable = [context.layer nextDrawable];
            id<MTLCommandBuffer> command = [context.queue commandBuffer];
            if (!drawable || !command || drawable.texture.device.registryID != context.registry ||
                drawable.texture.pixelFormat != MTLPixelFormatBGRA8Unorm) {
                @synchronized(context) {
                    row[@"error"] = @"screen-drawable-unavailable-or-wrong-device";
                    context.errors++; context.pending--;
                }
                dispatch_semaphore_signal(done); return;
            }
            MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
            pass.colorAttachments[0].texture = drawable.texture;
            pass.colorAttachments[0].loadAction = MTLLoadActionClear;
            pass.colorAttachments[0].storeAction = MTLStoreActionStore;
            pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
            id<MTLRenderCommandEncoder> encoder = [command renderCommandEncoderWithDescriptor:pass];
            if (!encoder) {
                @synchronized(context) {
                    row[@"error"] = @"screen-render-encoder-unavailable";
                    context.errors++; context.pending--;
                }
                dispatch_semaphore_signal(done); return;
            }
            double width = drawable.texture.width, height = drawable.texture.height;
            double scale = fmin(width / 1280.0, height / 720.0);
            MTLViewport viewport = {(width - 1280 * scale) / 2, (height - 720 * scale) / 2,
                                    1280 * scale, 720 * scale, 0, 1};
            [encoder setViewport:viewport];
            [encoder setRenderPipelineState:context.pipeline];
            [encoder setFragmentTexture:texture atIndex:0];
            [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [encoder endEncoding];
            @synchronized(context) {
                row[@"drawable_id"] = @(drawable.drawableID);
                row[@"drawable_registry_id"] = @(drawable.texture.device.registryID);
                row[@"drawable_width"] = @(drawable.texture.width);
                row[@"drawable_height"] = @(drawable.texture.height);
                row[@"drawable_pixel_format"] = @(drawable.texture.pixelFormat);
                row[@"geometry"] = @(geometry);
                row[@"submit_seconds"] = @(CACurrentMediaTime());
                row[@"presents_with_transaction"] = @(context.layer.presentsWithTransaction);
                row[@"viewport"] = @[@(viewport.originX), @(viewport.originY), @(viewport.width), @(viewport.height)];
            }
            [drawable addPresentedHandler:^(id<MTLDrawable> shown) {
                (void)texture;
                @synchronized(context) {
                    if ([row[@"drawable_presented"] boolValue]) { context.errors++; return; }
                    row[@"drawable_presented"] = @YES;
                    row[@"presented_seconds"] = @(shown.presentedTime);
                    row[@"presented_callback_seconds"] = @(CACurrentMediaTime());
                    retire(context, row, done);
                }
                MPCDiagnosticStage(@"linux-screen-drawable-presented", @{@"resource_id": @(resource),
                    @"generation": @(generation), @"phase": @(phase), @"presented_seconds": @(shown.presentedTime)});
                // Preserve the callback's actual timestamp, including zero.
                // A second API query is diagnostic only, never a CPU-time fallback.
                dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 100 * NSEC_PER_MSEC), context.renderQueue, ^{
                    @synchronized(context) {
                        row[@"presented_seconds_later_query"] = @(shown.presentedTime);
                        row[@"later_query_host_seconds"] = @(CACurrentMediaTime());
                    }
                });
            }];
            [command addCompletedHandler:^(id<MTLCommandBuffer> completed) {
                (void)texture; (void)drawable;
                @synchronized(context) {
                    if ([row[@"gpu_completed"] boolValue]) { context.errors++; return; }
                    row[@"gpu_completed"] = @YES;
                    row[@"consumer_status"] = @(completed.status);
                    row[@"consumer_error"] = @(completed.error != nil);
                    row[@"gpu_start_seconds"] = @(completed.GPUStartTime);
                    row[@"gpu_end_seconds"] = @(completed.GPUEndTime);
                    row[@"gpu_completed_callback_seconds"] = @(CACurrentMediaTime());
                    if (completed.status != MTLCommandBufferStatusCompleted || completed.error) context.errors++;
                    retire(context, row, done);
                }
                if (completedSource) completedSource((uint32_t)completed.status, completed.error != nil);
            }];
            [command addScheduledHandler:^(id<MTLCommandBuffer> scheduled) {
                @synchronized(context) {
                    row[@"scheduled_callback_seconds"] = @(CACurrentMediaTime());
                    row[@"scheduled_status"] = @(scheduled.status);
                }
                dispatch_async(dispatch_get_main_queue(), ^{
                    NSDictionary *stage = nil;
                    @synchronized(context) {
                        NSInteger state = UIApplication.sharedApplication.applicationState;
                        row[@"presentation_application_state"] = @(state);
                        row[@"presentation_on_main_thread"] = @(NSThread.isMainThread);
                        if (context.finished || context.interrupted || !context.visible || context.geometry != geometry ||
                            state != UIApplicationStateActive || row[@"error"] ||
                            scheduled.status == MTLCommandBufferStatusError || !context.layer.presentsWithTransaction) {
                            row[@"presentation_aborted"] = @YES;
                            row[@"error"] = @"scheduled-screen-presentation-rejected";
                            context.errors++;
                            retire(context, row, done);
                            stage = @{@"resource_id": @(resource), @"phase": @(phase),
                                @"application_state": @(state), @"interrupted": @(context.interrupted)};
                        } else {
                            row[@"presentation_enqueued_seconds"] = @(CACurrentMediaTime());
                        }
                    }
                    if (stage) { MPCDiagnosticStage(@"linux-screen-scheduled-present-rejected", stage); return; }
                    [CATransaction begin];
                    [CATransaction setDisableActions:YES];
                    [drawable present];
                    [CATransaction commit];
                    @synchronized(context) { row[@"presentation_call_completed"] = @YES; }
                    MPCDiagnosticStage(@"linux-screen-transaction-present-enqueued", @{@"resource_id": @(resource),
                        @"phase": @(phase), @"presentation_on_main_thread": @(NSThread.isMainThread)});
                });
            }];
            MPCDiagnosticStage(@"linux-screen-before-submit", @{@"resource_id": @(resource), @"phase": @(phase)});
            if (willSubmit && !willSubmit()) {
                @synchronized(context) {
                    row[@"error"] = @"source-lease-not-consumable";
                    context.errors++; context.pending--;
                }
                dispatch_semaphore_signal(done); return;
            }
            @synchronized(context) { row[@"gpu_submitted"] = @YES; }
            [command commit];
        }
    });
    if (dispatch_semaphore_wait(done, dispatch_time(DISPATCH_TIME_NOW, 5 * NSEC_PER_SEC))) {
        @synchronized(context) { context.errors++; context.interrupted = YES; row[@"error"] = @"screen-completion-or-presentation-timeout"; }
        MPCDiagnosticStage(@"linux-screen-presentation-timeout", @{@"resource_id": @(resource)});
    }
    @synchronized(context) { return [row copy]; }
}

NSDictionary *MPCGuestScreenConsume(const MPCNativeScanoutEvent *event, NSDictionary *image) {
    return consumeScreen(event, image, nil, nil);
}
NSDictionary *MPCGuestMovingScreenConsume(const MPCNativeScanoutEvent *event, NSDictionary *image,
    BOOL (^willSubmit)(void), void (^completed)(uint32_t, BOOL)) {
    return consumeScreen(event, image, willSubmit, completed);
}
NSDictionary *MPCGuestMovingScreenSnapshot(void) {
    if (!screen) return @{@"error": @"screen-not-created"};
    @synchronized(screen) {
        screen.finished = YES;
        NSMutableArray *copies = [NSMutableArray array];
        for (NSDictionary *row in screen.frames) [copies addObject:[row copy]];
        return @{@"schema": @1, @"scope": @"native-metal-three-buffer-changing-linux-screen",
            @"run": screen.nonce ?: @"", @"registry_id": @(screen.registry), @"frames": copies,
            @"errors": @(screen.errors), @"pending": @(screen.pending), @"interrupted": @(screen.interrupted),
            @"surface_visible": @(screen.visible), @"surface_geometry": @(screen.geometry),
            @"maximum_inflight": @1, @"drawable_limit": @2, @"lifecycle_events": [screen.lifecycle copy],
            @"presentation_route": @"scheduled-main-thread-core-animation-transaction",
            @"diagnostic_source_readbacks": @2, @"drawable_cpu_readbacks": @0};
    }
}

NSDictionary *MPCGuestScreenFinish(NSDictionary *imageImport, BOOL engineFinished) {
    if (!screen) return @{@"presentation_verified": @NO, @"reason": @"screen-not-created"};
    NSDictionary *native;
    @synchronized(screen) {
        NSMutableArray *copies = [NSMutableArray array];
        for (NSDictionary *row in screen.frames) [copies addObject:[row copy]];
        if (engineFinished) screen.finished = YES;
        native = @{@"schema": @2, @"scope": screen.frameSequence ? @"native-metal-eight-linux-frame-screen" : @"native-metal-two-linux-image-screen", @"run": screen.nonce ?: @"",
            @"registry_id": @(screen.registry), @"frames": copies, @"errors": @(screen.errors),
            @"pending": @(screen.pending), @"interrupted": @(screen.interrupted), @"surface_visible": @(screen.visible),
            @"surface_geometry": @(screen.geometry), @"maximum_inflight": @1, @"drawable_limit": @2,
            @"presentation_route": @"scheduled-main-thread-core-animation-transaction",
            @"lifecycle_events": [screen.lifecycle copy],
            @"diagnostic_source_readbacks": @2, @"drawable_cpu_readbacks": @0,
            @"continuous_animation_verified": @NO, @"frame_pacing_verified": @NO,
            @"zero_copy_transport_verified": @NO, @"gameplay_verified": @NO};
    }
    return screen.frameSequence ? MPCValidateGuestFrameScreen(screen.nonce ?: @"", imageImport, native, engineFinished) : MPCValidateGuestScreen(screen.nonce ?: @"", imageImport, native, engineFinished);
}
