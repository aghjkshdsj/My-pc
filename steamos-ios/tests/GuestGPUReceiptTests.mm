#import "ProbeBridge.h"
#include <stdio.h>
#include <stdlib.h>

// Protocol fixtures exercise the production validator. They are not device,
// shader, memory-import or Metal results.
static NSString *nonce = @"0123456789abcdef0123456789abcdef";
static NSString *json(NSDictionary *value) {
    return [[NSString alloc] initWithData:[NSJSONSerialization dataWithJSONObject:value options:0 error:nil]
                                encoding:NSUTF8StringEncoding];
}
static NSMutableDictionary *device(void) {
    NSMutableDictionary *parameters = [NSMutableDictionary dictionary];
    for (NSString *key in @[@"1", @"3", @"4", @"6"]) parameters[key] = @{@"supported": @YES, @"value": @1};
    return [@{@"run": nonce, @"driver": @"virtio_gpu", @"page_bytes": @4096, @"parameters": parameters} mutableCopy];
}
static NSMutableDictionary *draw(void) {
    return [@{@"machine": @"aarch64", @"software": @NO, @"width": @1280, @"height": @720,
        @"shader_phases": @2, @"pixels_checked": @1843200, @"mismatches": @0,
        @"channel_sum": @1219256320LL, @"validation_errors": @0, @"metal_host_verified": @NO,
        @"presentation_verified": @NO, @"game_fps_verified": @NO} mutableCopy];
}
static NSString *serial(NSDictionary *gpu, NSDictionary *pixels) {
    return [NSString stringWithFormat:@"MPC_GPU_GUEST_RUN=%@\nMPC_GPU_KERNEL %@\nMPC_VK_DIAGNOSTIC %@\nMPC_GPU_GUEST_EXIT=0\n",
            nonce, json(gpu), json(pixels)];
}
static unsigned checks;
static void check(BOOL value, const char *message) {
    ++checks;
    if (!value) { fprintf(stderr, "Guest GPU receipt check failed: %s\n", message); exit(1); }
}
static void rejected(NSString *text, const char *message, BOOL linuxPassed = YES) {
    check([MPCParseGuestGPUReceipt(text, nonce, linuxPassed)[@"guest_vulkan_pixels_verified"] isEqual:@NO], message);
}
int main(void) {
    @autoreleasepool {
        NSString *valid = serial(device(), draw());
        NSDictionary *result = MPCParseGuestGPUReceipt(valid, nonce, YES);
        check([result[@"guest_vulkan_pixels_verified"] isEqual:@YES], "matching protocol fixture");
        check([result[@"metal_host_verified"] isEqual:@NO] && [result[@"host_memory_import_verified"] isEqual:@NO],
              "guest receipt cannot independently claim host proof");
        rejected(valid, "Linux ABI failure", NO);
        rejected(@"", "empty serial");
        rejected([valid stringByReplacingOccurrencesOfString:nonce withString:@"ffffffffffffffffffffffffffffffff"], "stale nonce");
        rejected([@"MPC_GPU_GUEST_RUN=ffffffffffffffffffffffffffffffff\n" stringByAppendingString:valid], "extra stale run marker");
        rejected([valid stringByAppendingString:@"MPC_GPU_GUEST_EXIT=0\n"], "duplicate exit");
        rejected([valid stringByReplacingOccurrencesOfString:@"MPC_GPU_GUEST_EXIT=0" withString:@"MPC_GPU_GUEST_EXIT=3"], "Vulkan failure");
        rejected([valid stringByAppendingFormat:@"MPC_VK_DIAGNOSTIC %@\n", json(draw())], "duplicate draw");
        rejected([valid stringByAppendingString:@"MPC_VK_DIAGNOSTIC invalid-json\n"], "malformed duplicate draw");
        for (NSString *key in @[@"software", @"metal_host_verified", @"presentation_verified", @"game_fps_verified"]) {
            NSMutableDictionary *row = draw(); row[key] = @YES;
            rejected(serial(device(), row), key.UTF8String);
        }
        for (NSString *key in @[@"width", @"height", @"shader_phases", @"pixels_checked", @"channel_sum"]) {
            NSMutableDictionary *row = draw(); row[key] = @0;
            rejected(serial(device(), row), key.UTF8String);
        }
        for (NSString *key in @[@"mismatches", @"validation_errors"]) {
            NSMutableDictionary *row = draw(); row[key] = @1;
            rejected(serial(device(), row), key.UTF8String);
        }
        NSMutableDictionary *malformed = draw(); malformed[@"channel_sum"] = NSNull.null;
        rejected(serial(device(), malformed), "null checksum");
        NSMutableDictionary *wrongDriver = device(); wrongDriver[@"driver"] = @"fixture";
        rejected(serial(wrongDriver, draw()), "wrong DRM driver");
        for (NSString *key in @[@"1", @"3", @"4", @"6"]) {
            NSMutableDictionary *gpu = device(); gpu[@"parameters"][key] = @{@"supported": @YES, @"value": @0};
            rejected(serial(gpu, draw()), key.UTF8String);
        }
        rejected([NSString stringWithFormat:@"MPC_VK_DIAGNOSTIC %@\nMPC_GPU_GUEST_RUN=%@\nMPC_GPU_KERNEL %@\nMPC_GPU_GUEST_EXIT=0\n", json(draw()), nonce, json(device())], "draw preceding fresh run");
        printf("GUEST_GPU_RECEIPT_TESTS_PASSED checks=%u scope=protocol-fixtures-only\n", checks);
    }
    return 0;
}
