#import <Foundation/Foundation.h>
#import "GuestImageImport.h"

static NSString *nonce = @"0123456789abcdef0123456789abcdef";
static NSString *line(NSString *prefix, NSDictionary *value) {
    return [prefix stringByAppendingString:[[NSString alloc] initWithData:
        [NSJSONSerialization dataWithJSONObject:value options:0 error:nil] encoding:NSUTF8StringEncoding]];
}
static NSMutableDictionary *producer(unsigned phase, unsigned resource) {
    return [@{@"schema": @1, @"run": nonce, @"phase": @(phase), @"resource_id": @(resource),
        @"tiling": @"drm-format-modifier", @"drm_modifier": @0, @"memory_plane": @0,
        @"width": @1280, @"height": @720, @"row_pitch": @5120, @"offset": @0,
        @"allocation_bytes": @3686400, @"producer_fence_completed": @YES, @"external_queue_release": @YES} mutableCopy];
}
static NSMutableDictionary *image(unsigned phase, unsigned resource, unsigned generation, uint64_t sum) {
    return [@{@"phase": @(phase), @"resource_id": @(resource), @"generation": @(generation),
        @"width": @1280, @"height": @720, @"row_pitch": @5120, @"offset": @0,
        @"backing_bytes": @3686400, @"native_registry_id": @77, @"native_buffer_alias_verified": @YES,
        @"pixels_checked": @921600, @"mismatches": @0, @"channel_sum": @(sum),
        @"consumer_status": @4, @"consumer_error": @NO} mutableCopy];
}
static NSDictionary *native(NSArray *images) {
    NSMutableArray *events = [NSMutableArray array];
    for (unsigned i = 0; i < 6; ++i)
        [events addObject:@{@"sequence": @(i + 1), @"kind": @(i % 3 + 1),
                           @"generation": @(i < 3 ? 1 : 2), @"resource_id": @(i < 3 ? 12 : 19)}];
    return @{@"scope": @"native-metal-linux-linear-image-import", @"run": nonce, @"images": images,
        @"events": events, @"errors": @0, @"active": @NO, @"reading": @NO, @"registry_id": @77};
}
static NSString *serial(NSArray *producers, NSDictionary *exit) {
    NSMutableArray *lines = [NSMutableArray array];
    for (NSDictionary *p in producers) [lines addObject:line(@"MPC_IMAGE_PRODUCER ", p)];
    [lines addObject:line(@"MPC_IMAGE_EXIT ", exit)];
    [lines addObject:@"MPC_IMAGE_GUEST_EXIT=0"];
    return [lines componentsJoinedByString:@"\n"];
}
static unsigned checks;
static void expect(BOOL actual, BOOL wanted) { if (actual != wanted) abort(); checks++; }
static BOOL accepted(NSString *text, NSDictionary *n, BOOL engine, BOOL linux, BOOL metal) {
    NSDictionary *r = MPCValidateGuestImageImport(text, nonce, n, engine, linux, metal);
    if ([r[@"presentation_verified"] boolValue] || [r[@"gameplay_verified"] boolValue] ||
        [r[@"zero_copy_transport_verified"] boolValue]) abort();
    return [r[@"host_memory_import_verified"] boolValue];
}
int main(void) { @autoreleasepool {
    NSMutableDictionary *p0 = producer(0, 12), *p1 = producer(41, 19);
    NSMutableDictionary *i0 = image(0, 12, 1, 615690240), *i1 = image(41, 19, 2, 603566080);
    NSDictionary *exit = @{@"schema": @1, @"run": nonce, @"status": @0, @"phases": @2,
        @"scanout_disabled": @YES, @"images_released": @YES};
    NSString *valid = serial(@[p0, p1], exit);
    NSDictionary *n = native(@[i0, i1]);
    expect(accepted(valid, n, YES, YES, YES), YES);
    expect(accepted(valid, n, NO, YES, YES), NO);
    expect(accepted(valid, n, YES, NO, YES), NO);
    expect(accepted(valid, n, YES, YES, NO), NO);
    for (NSString *key in @[@"tiling", @"drm_modifier", @"memory_plane"]) {
        NSMutableDictionary *wrong = [p0 mutableCopy];
        wrong[key] = [key isEqual:@"tiling"] ? @"linear-legacy" : @1;
        expect(accepted(serial(@[wrong, p1], exit), n, YES, YES, YES), NO);
    }
    NSMutableDictionary *missingModifier = [p0 mutableCopy]; [missingModifier removeObjectForKey:@"drm_modifier"];
    expect(accepted(serial(@[missingModifier, p1], exit), n, YES, YES, YES), NO);
    for (NSString *key in @[@"producer_fence_completed", @"external_queue_release", @"width", @"height", @"schema"])
    {
        NSMutableDictionary *bad = [p0 mutableCopy]; bad[key] = @0;
        expect(accepted(serial(@[bad, p1], exit), n, YES, YES, YES), NO);
    }
    for (NSString *key in @[@"resource_id", @"phase", @"row_pitch", @"offset", @"run"])
    {
        NSMutableDictionary *bad = [p1 mutableCopy]; bad[key] = [key isEqual:@"run"] ? @"stale" : @99;
        expect(accepted(serial(@[p0, bad], exit), n, YES, YES, YES), NO);
    }
    for (NSString *key in @[@"mismatches", @"consumer_status", @"consumer_error", @"native_registry_id",
                           @"backing_bytes", @"native_buffer_alias_verified", @"pixels_checked", @"channel_sum"])
    {
        NSMutableDictionary *bad = [i1 mutableCopy]; bad[key] = @99;
        expect(accepted(valid, native(@[i0, bad]), YES, YES, YES), NO);
    }
    NSMutableDictionary *bad = [i1 mutableCopy]; bad[@"generation"] = @1;
    expect(accepted(valid, native(@[i0, bad]), YES, YES, YES), NO);
    expect(accepted(valid, native(@[i0]), YES, YES, YES), NO);
    expect(accepted(valid, native(@[i0, NSNull.null]), YES, YES, YES), NO);
    for (NSString *key in @[@"active", @"reading", @"errors"]) {
        NSMutableDictionary *badNative = [n mutableCopy]; badNative[key] = @1;
        expect(accepted(valid, badNative, YES, YES, YES), NO);
    }
    expect(accepted([valid stringByAppendingString:@"\nMPC_IMAGE_GUEST_EXIT=0"], n, YES, YES, YES), NO);
    expect(accepted([valid stringByAppendingString:@"\nMPC_IMAGE_REJECTED {}"], n, YES, YES, YES), NO);
    expect(accepted(serial(@[p0, p0, p1], exit), n, YES, YES, YES), NO);
    NSMutableDictionary *badExit = [exit mutableCopy]; badExit[@"images_released"] = @NO;
    expect(accepted(serial(@[p0, p1], badExit), n, YES, YES, YES), NO);
    NSMutableDictionary *missingEvents = [n mutableCopy]; missingEvents[@"events"] = @[];
    expect(accepted(valid, missingEvents, YES, YES, YES), NO);
    printf("GUEST_IMAGE_RECEIPT_TESTS_OK checks=%u; fixtures are not phone import evidence\n", checks);
} }
