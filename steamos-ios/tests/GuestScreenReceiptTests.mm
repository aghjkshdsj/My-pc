#import "GuestScreenPresentation.h"
#include <cmath>
static unsigned checks;
static NSString *nonce = @"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
static NSMutableDictionary *imported(void) {
    return [@{@"run": nonce, @"host_memory_import_verified": @YES,
        @"native": @{@"registry_id": @77, @"images": @[
            @{@"resource_id": @10, @"generation": @1, @"phase": @0},
            @{@"resource_id": @11, @"generation": @3, @"phase": @41}]}} mutableCopy];
}
static NSMutableDictionary *frame(unsigned i) {
    double time = i ? 3 : 1;
    return [@{@"frame_index": @(i+1), @"resource_id": @(i ? 11 : 10), @"generation": @(i ? 3 : 1),
        @"phase": @(i ? 41 : 0), @"source_registry_id": @77, @"drawable_registry_id": @77,
        @"source_is_imported_guest_texture": @YES, @"source_width": @1280, @"source_height": @720,
        @"source_pixel_format": @80, @"drawable_pixel_format": @80, @"geometry": @1,
        @"gpu_completed": @YES, @"drawable_presented": @YES, @"consumer_status": @4, @"consumer_error": @NO,
        @"drawable_id": @(i), @"drawable_width": @1280, @"drawable_height": @720,
        @"viewport": @[@0, @0, @1280, @720], @"submit_seconds": @(time),
        @"gpu_start_seconds": @(time+.001), @"gpu_end_seconds": @(time+.002),
        @"presented_seconds": @(time+.016)} mutableCopy];
}
static NSMutableDictionary *native(void) {
    return [@{@"schema": @1, @"scope": @"native-metal-two-linux-image-screen", @"run": nonce,
        @"registry_id": @77, @"frames": @[frame(0), frame(1)], @"errors": @0, @"pending": @0,
        @"interrupted": @NO, @"surface_visible": @YES, @"surface_geometry": @1,
        @"maximum_inflight": @1, @"drawable_limit": @2, @"diagnostic_source_readbacks": @2,
        @"drawable_cpu_readbacks": @0, @"continuous_animation_verified": @NO,
        @"frame_pacing_verified": @NO, @"zero_copy_transport_verified": @NO, @"gameplay_verified": @NO} mutableCopy];
}
static void expect(NSDictionary *n, NSDictionary *image, BOOL engine, BOOL wanted) {
    NSDictionary *r = MPCValidateGuestScreen(nonce, image, n, engine);
    if ([r[@"presentation_verified"] boolValue] != wanted) abort();
    for (NSString *k in @[@"continuous_animation_verified", @"frame_pacing_verified", @"zero_copy_transport_verified", @"gameplay_verified"])
        if ([r[k] boolValue]) abort();
    checks++;
}
int main(void) { @autoreleasepool {
    expect(native(), imported(), YES, YES);
    expect(native(), imported(), NO, NO);
    NSMutableDictionary *image = imported(); image[@"host_memory_import_verified"] = @NO;
    expect(native(), image, YES, NO);
    image = imported(); image[@"run"] = @"old"; expect(native(), image, YES, NO);
    NSDictionary *badNative = @{@"run": @"old", @"scope": @"offscreen", @"registry_id": @88,
        @"errors": @1, @"pending": @1, @"interrupted": @YES, @"surface_visible": @NO,
        @"maximum_inflight": @3, @"drawable_limit": @3, @"diagnostic_source_readbacks": @0,
        @"drawable_cpu_readbacks": @1, @"continuous_animation_verified": @YES,
        @"frame_pacing_verified": @YES, @"zero_copy_transport_verified": @YES, @"gameplay_verified": @YES};
    for (NSString *k in badNative) {
        NSMutableDictionary *n = native(); n[k] = badNative[k]; expect(n, imported(), YES, NO);
    }
    NSDictionary *badFrame = @{@"frame_index": @3, @"resource_id": @99, @"generation": @9, @"phase": @1,
        @"source_registry_id": @88, @"drawable_registry_id": @88, @"source_is_imported_guest_texture": @NO,
        @"source_width": @1279, @"source_height": @719, @"source_pixel_format": @70,
        @"drawable_pixel_format": @70, @"geometry": @2, @"gpu_completed": @NO, @"drawable_presented": @NO,
        @"consumer_status": @5, @"consumer_error": @YES, @"drawable_width": @0, @"drawable_height": @0,
        @"submit_seconds": @0, @"gpu_start_seconds": @0, @"gpu_end_seconds": @0, @"presented_seconds": @0};
    for (NSString *k in badFrame) {
        NSMutableDictionary *n = native(), *f = frame(1); f[k] = badFrame[k]; n[@"frames"] = @[frame(0), f];
        expect(n, imported(), YES, NO);
        [f removeObjectForKey:k]; expect(n, imported(), YES, NO);
    }
    for (NSString *k in @[@"gpu_start_seconds", @"gpu_end_seconds", @"presented_seconds"]) {
        NSMutableDictionary *n = native(), *f = frame(1); f[k] = @(NAN); n[@"frames"] = @[frame(0), f];
        expect(n, imported(), YES, NO);
    }
    for (NSArray *frames in @[@[], @[frame(0)], @[frame(1), frame(0)], @[frame(0), frame(0)]]) {
        NSMutableDictionary *n = native(); n[@"frames"] = frames; expect(n, imported(), YES, NO);
    }
    NSMutableDictionary *n = native(), *f = frame(1); f[@"error"] = @"timed-out"; n[@"frames"] = @[frame(0), f];
    expect(n, imported(), YES, NO);
    f = frame(1); f[@"viewport"] = @[@0, @0, @720, @1280]; n[@"frames"] = @[frame(0), f]; expect(n, imported(), YES, NO);
    f = frame(1); [f removeObjectForKey:@"drawable_id"]; n[@"frames"] = @[frame(0), f]; expect(n, imported(), YES, NO);
    f = frame(1); f[@"gpu_end_seconds"] = @4; n[@"frames"] = @[frame(0), f]; expect(n, imported(), YES, NO);
    // A drawable ID may be reused; resource/phase identity and display order decide acceptance.
    f = frame(1); f[@"drawable_id"] = @0; n[@"frames"] = @[frame(0), f]; expect(n, imported(), YES, YES);
    printf("GUEST_SCREEN_RECEIPT_FIXTURES_OK checks=%u scope=synthetic-no-device-acceptance\n", checks);
} }
