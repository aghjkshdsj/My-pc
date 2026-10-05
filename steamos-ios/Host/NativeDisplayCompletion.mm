/* SPDX-License-Identifier: MIT
 * Generic bounded asynchronous native consumer; no diagnostic pattern/UART. */
#import "NativeDisplayCompletion.h"
#import <Metal/Metal.h>
#import <QuartzCore/CAMetalLayer.h>
#include <dlfcn.h>
#include "../Engine/NativeCompletionABI.h"

@interface MPCNativeCompletionContext : NSObject
@property(nonatomic,strong) CAMetalLayer *layer;
@property(nonatomic,strong) id<MTLDevice> device;
@property(nonatomic,strong) id<MTLCommandQueue> queue;
@property(nonatomic,strong) id<MTLRenderPipelineState> pipeline;
@property(nonatomic,strong) dispatch_queue_t executor;
@property(nonatomic,strong) NSMutableDictionary<NSNumber *,NSNumber *> *installed;
@property(nonatomic,strong) NSMutableDictionary<NSString *,NSNumber *> *tickets;
@property(nonatomic,strong) NSMutableArray<NSDictionary *> *terminals;
@property(nonatomic) MPCCompleteNativeRead complete;
@property(nonatomic) MPCCancelNativeRead cancel;
@property(nonatomic) uint64_t sequence, accepted, completed, gpuErrors, canceled, rejected, invalidCompletions;
@property(nonatomic) NSUInteger pending, maxPending;
@property(nonatomic) NSUInteger completing;
@property(nonatomic) uint64_t retainedBytes, peakRetainedBytes;
@property(nonatomic) double gpuSeconds;
@end
@implementation MPCNativeCompletionContext
@end
/* Never unload the library or release its configured context while callbacks
 * are possible. Engine reset/unrealize separately drains outstanding reads. */
static MPCNativeCompletionContext *nativeCompletion;
static NSString *ticketKey(MPCNativeReadToken t)
{ return [NSString stringWithFormat:@"%llu:%llu:%llu",(unsigned long long)t.session,
    (unsigned long long)t.command,(unsigned long long)t.reader]; }

static void finish(MPCNativeCompletionContext *c, MPCNativeReadToken t,
                   NSString *key, BOOL submitted, id<MTLCommandBuffer> command)
{
    // A submitted command remains owned until a real terminal callback.
    if (submitted && command.status != MTLCommandBufferStatusCompleted &&
        command.status != MTLCommandBufferStatusError) return;
    @synchronized(c) {
        NSNumber *bytes=c.tickets[key];
        if (!bytes) { c.invalidCompletions++; return; }
        c.retainedBytes-=bytes.unsignedLongLongValue;
        [c.tickets removeObjectForKey:key]; c.pending--; c.completing++;
        if (!submitted) c.canceled++;
        else if (command.status == MTLCommandBufferStatusError) c.gpuErrors++;
        else {
            c.completed++;
            if (command.GPUStartTime > 0 && command.GPUEndTime >= command.GPUStartTime)
                c.gpuSeconds += command.GPUEndTime - command.GPUStartTime;
        }
    }
    int accepted = submitted ? c.complete(&t,(uint32_t)command.status) : c.cancel(&t);
    @synchronized(c) {
        if (!accepted) c.invalidCompletions++;
        c.completing--;
        if (c.terminals.count==64) [c.terminals removeObjectAtIndex:0];
        [c.terminals addObject:@{@"session":@(t.session),@"command":@(t.command),
            @"reader":@(t.reader),@"generation":@(t.generation),@"resource_id":@(t.resource_id),
            @"gpu_command_submitted":@(submitted),@"actual_metal_status":@(submitted?command.status:0),
            @"actual_metal_error_code":@(submitted?command.error.code:0),
            @"gpu_start_seconds":@(submitted?command.GPUStartTime:0),
            @"gpu_end_seconds":@(submitted?command.GPUEndTime:0),
            @"engine_terminal_accepted":@(accepted!=0)}];
    }
}

static BOOL validateImage(MPCNativeCompletionContext *c, MPCNativeScanoutEvent e,
                          id<MTLTexture> texture, id<MTLBuffer> backing)
{
    if (!texture || !backing || backing.length > 32u*1024u*1024u ||
        !e.width || !e.height || e.width > 8192 || e.height > 8192 ||
        !e.crop_width || !e.crop_height || e.x > e.width || e.y > e.height ||
        e.crop_width > e.width-e.x || e.crop_height > e.height-e.y ||
        e.format != 2 /* virtio B8G8R8X8_UNORM */ || e.y_0_top > 1 ||
        texture.device.registryID != c.device.registryID || backing.device.registryID != c.device.registryID ||
        texture.pixelFormat != MTLPixelFormatBGRA8Unorm || texture.textureType != MTLTextureType2D ||
        texture.width != e.width || texture.height != e.height || texture.depth != 1 ||
        texture.sampleCount != 1 || texture.mipmapLevelCount != 1 || texture.arrayLength != 1 ||
        texture.storageMode != MTLStorageModeShared || backing.storageMode != MTLStorageModeShared ||
        texture.bufferOffset != e.offset || texture.bufferBytesPerRow != e.stride ||
        e.stride < (uint64_t)e.width*4 || e.offset > backing.length ||
        (uint64_t)e.stride*e.height > backing.length-e.offset) return NO;
    NSUInteger alignment=[c.device minimumLinearTextureAlignmentForPixelFormat:texture.pixelFormat];
    return alignment && !(e.offset%alignment) && !(e.stride%alignment);
}

static int nativeEvent(void *opaque,const MPCNativeCompletionEvent *event)
{
    @autoreleasepool {
        MPCNativeCompletionContext *c=(__bridge MPCNativeCompletionContext *)opaque;
        if (!event || event->abi!=2 || event->bytes!=sizeof(*event) ||
            event->image.abi!=1 || event->image.bytes!=sizeof(event->image)) return 0;
        MPCNativeScanoutEvent image=event->image;
        MPCNativeReadToken token=event->token;
        NSString *key=nil;
        // Retain the borrowed native texture AND backing before acceptance.
        id<MTLTexture> texture=nil;
        id<MTLBuffer> backing=nil;
        if (image.kind==MPC_SCANOUT_INSTALL || image.kind==MPC_SCANOUT_FLUSH) {
            texture=(__bridge id<MTLTexture>)image.texture;
            backing=texture.buffer;
        }
        @synchronized(c) {
            if (!image.sequence || image.sequence <= c.sequence || !image.resource_id || !image.generation) {
                c.rejected++; return 0;
            }
            c.sequence=image.sequence;
            NSNumber *generation=@(image.generation);
            if (image.kind==MPC_SCANOUT_DISABLE) {
                if ([c.installed[generation] unsignedIntValue]!=image.resource_id) { c.rejected++; return 0; }
                [c.installed removeObjectForKey:generation]; return 1;
            }
            if (image.kind==MPC_SCANOUT_INSTALL) {
                if (c.installed.count>=16 || c.installed[generation] || token.reader ||
                    !validateImage(c,image,texture,backing)) { c.rejected++; return 0; }
                c.installed[generation]=@(image.resource_id); return 1;
            }
            if (image.kind!=MPC_SCANOUT_FLUSH ||
                [c.installed[generation] unsignedIntValue]!=image.resource_id ||
                !token.session || !token.command || !token.reader || token.reserved ||
                token.resource_id!=image.resource_id || token.generation!=image.generation ||
                c.pending>=16 || !validateImage(c,image,texture,backing)) { c.rejected++; return 0; }
            key=ticketKey(token);
            if (c.tickets[key] || backing.length > 128u*1024u*1024u-c.retainedBytes) { c.rejected++; return 0; }
            c.tickets[key]=@(backing.length); c.accepted++; c.pending++;
            c.retainedBytes+=backing.length;
            c.peakRetainedBytes=MAX(c.peakRetainedBytes,c.retainedBytes);
            c.maxPending=MAX(c.maxPending,c.pending);
        }
        dispatch_async(c.executor, ^{
            @autoreleasepool {
                id<CAMetalDrawable> drawable=[c.layer nextDrawable];
                id<MTLCommandBuffer> command=[c.queue commandBuffer];
                if (!drawable || !command || drawable.texture.device.registryID!=c.device.registryID ||
                    drawable.texture.pixelFormat!=MTLPixelFormatBGRA8Unorm || c.layer.presentsWithTransaction) {
                    finish(c,token,key,NO,nil); return;
                }
                MTLRenderPassDescriptor *pass=[MTLRenderPassDescriptor renderPassDescriptor];
                pass.colorAttachments[0].texture=drawable.texture;
                pass.colorAttachments[0].loadAction=MTLLoadActionDontCare;
                pass.colorAttachments[0].storeAction=MTLStoreActionStore;
                id<MTLRenderCommandEncoder> encoder=[command renderCommandEncoderWithDescriptor:pass];
                if (!encoder) { finish(c,token,key,NO,nil); return; }
                float crop[8]={(float)image.x/image.width,(float)image.y/image.height,
                    (float)image.crop_width/image.width,(float)image.crop_height/image.height,
                    image.y_0_top ? 1.0f : 0.0f,0,0,0};
                [encoder setRenderPipelineState:c.pipeline];
                [encoder setFragmentTexture:texture atIndex:0];
                [encoder setFragmentBytes:crop length:sizeof(crop) atIndex:0];
                [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
                [encoder endEncoding];
                [command presentDrawable:drawable];
                [command addCompletedHandler:^(id<MTLCommandBuffer> terminal) {
                    // These strong captures survive even a backgrounded surface,
                    // failed draw or shutdown request. No timeout releases them.
                    (void)texture; (void)backing; (void)drawable;
                    finish(c,token,key,YES,terminal);
                }];
                [command commit];
            }
        });
        return 1;
    }
}

BOOL MPCNativeDisplayCompletionBegin(void *engine,CAMetalLayer *layer,NSError **error)
{
    NSCAssert(NSThread.isMainThread,@"Prepare the stable native surface on main");
    auto configure=reinterpret_cast<MPCConfigureNativeCompletion>(dlsym(engine,"mpc_qemu_configure_native_completion"));
    auto complete=reinterpret_cast<MPCCompleteNativeRead>(dlsym(engine,"mpc_qemu_complete_native_read"));
    auto cancel=reinterpret_cast<MPCCancelNativeRead>(dlsym(engine,"mpc_qemu_cancel_native_read"));
    if (!engine || !configure || !complete || !cancel || nativeCompletion || !layer.device ||
        layer.pixelFormat!=MTLPixelFormatBGRA8Unorm || layer.presentsWithTransaction ||
        !layer.allowsNextDrawableTimeout) {
        if(error)*error=[NSError errorWithDomain:@"NativeCompletion" code:1 userInfo:@{
            NSLocalizedDescriptionKey:@"Exclusive native completion ABI2 and a stable pure-Metal surface are required."}];
        return NO;
    }
    MPCNativeCompletionContext *c=[MPCNativeCompletionContext new];
    c.layer=layer;c.device=layer.device;c.complete=complete;c.cancel=cancel;
    c.queue=[c.device newCommandQueue];
    c.executor=dispatch_queue_create("com.mypc.native-display-completion",DISPATCH_QUEUE_SERIAL);
    c.installed=[NSMutableDictionary dictionary];c.tickets=[NSMutableDictionary dictionary];
    c.terminals=[NSMutableArray array];
    NSString *source=@"#include <metal_stdlib>\nusing namespace metal;\n"
        "struct V { float4 p [[position]]; float2 uv; };\n"
        "vertex V nativeVertex(uint i [[vertex_id]]) { float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};"
        "V o; o.p=float4(p[i],0,1); o.uv=float2((p[i].x+1)*.5,(1-p[i].y)*.5); return o; }\n"
        "fragment float4 nativeFragment(V v [[stage_in]], texture2d<float> t [[texture(0)]],constant float4 *c [[buffer(0)]]) {"
        "float2 uv=v.uv; if(c[1].x>0.5)uv.y=1-uv.y; uv=c[0].xy+uv*c[0].zw;"
        "constexpr sampler s(coord::normalized,address::clamp_to_edge,filter::linear); return float4(t.sample(s,uv).rgb,1); }\n";
    NSError *buildError=nil;
    id<MTLLibrary> library=[c.device newLibraryWithSource:source options:nil error:&buildError];
    MTLRenderPipelineDescriptor *desc=[MTLRenderPipelineDescriptor new];
    desc.vertexFunction=[library newFunctionWithName:@"nativeVertex"];
    desc.fragmentFunction=[library newFunctionWithName:@"nativeFragment"];
    desc.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    if(library)c.pipeline=[c.device newRenderPipelineStateWithDescriptor:desc error:&buildError];
    if(!c.queue || !c.pipeline || configure(2,sizeof(MPCNativeCompletionEvent),nativeEvent,(__bridge void *)c)!=1) {
        if(error)*error=buildError ?: [NSError errorWithDomain:@"NativeCompletion" code:2 userInfo:@{
            NSLocalizedDescriptionKey:@"Native Metal pipeline or exclusive engine configuration failed."}];
        return NO;
    }
    nativeCompletion=c;return YES;
}

NSDictionary *MPCNativeDisplayCompletionReport(void)
{
    MPCNativeCompletionContext *c=nativeCompletion;
    if(!c)return @{@"scope":@"native-completion-host-source",@"configured":@NO,@"phone_verified":@NO};
    @synchronized(c) {
        return @{@"scope":@"native-completion-host-observations",@"configured":@YES,
            @"accepted_readers":@(c.accepted),@"actual_gpu_completed":@(c.completed),
            @"actual_gpu_errors":@(c.gpuErrors),@"canceled_before_submission":@(c.canceled),
            @"rejected_events":@(c.rejected),@"invalid_completions":@(c.invalidCompletions),
            @"pending_readers":@(c.pending),@"max_pending_readers":@(c.maxPending),
            @"completion_callbacks_in_progress":@(c.completing),@"recent_terminals":[c.terminals copy],
            @"retained_backing_bytes":@(c.retainedBytes),@"peak_retained_backing_bytes":@(c.peakRetainedBytes),
            @"retained_backing_budget_bytes":@(128u*1024u*1024u),
            @"installed_images":@(c.installed.count),@"gpu_seconds_sum":@(c.gpuSeconds),
            @"desktop_verified":@NO,@"steam_verified":@NO,@"gameplay_verified":@NO,
            @"producer_dependency_verified":@NO,@"display_timing_verified":@NO};
    }
}
