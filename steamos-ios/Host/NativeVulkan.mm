#import "ProbeBridge.h"
#include <CommonCrypto/CommonDigest.h>
#include <dlfcn.h>

extern "C" int MPCNativeVulkanDraw(void *, const char *, const char *);
static NSString *digest(NSData *data) {
    unsigned char value[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(data.bytes, static_cast<CC_LONG>(data.length), value);
    NSMutableString *text = [NSMutableString string];
    for (unsigned char byte : value) [text appendFormat:@"%02x", byte];
    return text;
}
NSDictionary *MPCNativeVulkanProbe(NSString *diagnosticDirectory) {
    @autoreleasepool {
        NSString *root = NSBundle.mainBundle.bundlePath;
        NSString *payload = [root stringByAppendingPathComponent:@"NativeVulkan"];
        NSString *framework = [root stringByAppendingPathComponent:@"Frameworks/MoltenVK.framework/MoltenVK"];
        NSData *inputs = [NSData dataWithContentsOfFile:[payload stringByAppendingPathComponent:@"payload-receipt.json"]];
        NSDictionary *receipt = inputs ? [NSJSONSerialization JSONObjectWithData:inputs options:0 error:nil] : nil;
        if (![receipt isKindOfClass:NSDictionary.class])
            return @{@"status": @"unavailable", @"reason": @"Install the native Vulkan engine-bearing prerelease.",
                @"linux_graphics": @NO, @"presentation_verified": @NO, @"gameplay_verified": @NO};
        if (![receipt[@"scope"] isEqual:@"bundled-native-ios-vulkan-diagnostic"])
            return @{@"status": @"failed", @"stage": @"payload-scope", @"linux_graphics": @NO};
        for (NSString *name in @[@"MoltenVK", @"vertex.spv", @"fragment.spv"]) {
            NSString *path = [name isEqual:@"MoltenVK"] ? framework : [payload stringByAppendingPathComponent:name];
            NSData *data = [NSData dataWithContentsOfFile:path options:NSDataReadingMappedIfSafe error:nil];
            NSDictionary *expected = receipt[@"files"][name];
            if (!data || data.length != [expected[@"bytes"] unsignedLongLongValue] ||
                ![digest(data) isEqual:expected[@"sha256"]])
                return @{@"status": @"failed", @"stage": @"payload-sha256", @"input": name, @"linux_graphics": @NO};
        }
        MPCDiagnosticStage(@"native-vulkan-before-dlopen", @{});
        // Load inside the durable test capture, never as a required app-startup dependency.
        static void *library = nullptr;
        if (!library) library = dlopen(framework.fileSystemRepresentation, RTLD_NOW | RTLD_LOCAL);
        if (!library) return @{@"status": @"failed", @"stage": @"moltenvk-dlopen",
            @"reason": [NSString stringWithUTF8String:dlerror()] ?: @"Loader error", @"linux_graphics": @NO};
        MPCDiagnosticStage(@"native-vulkan-engine-loaded", @{});
        NSString *vertex = [payload stringByAppendingPathComponent:@"vertex.spv"];
        NSString *fragment = [payload stringByAppendingPathComponent:@"fragment.spv"];
        MPCDiagnosticStage(@"native-vulkan-before-two-shader-draws", @{});
        double start = NSProcessInfo.processInfo.systemUptime;
        int result = MPCNativeVulkanDraw(library, vertex.fileSystemRepresentation, fragment.fileSystemRepresentation);
        double elapsed = (NSProcessInfo.processInfo.systemUptime - start) * 1000;
        MPCDiagnosticStage(@"native-vulkan-draw-returned", @{@"exit_status": @(result)});
        NSString *output = [NSString stringWithContentsOfFile:[diagnosticDirectory stringByAppendingPathComponent:@"engine-output.log"]
            encoding:NSUTF8StringEncoding error:nil] ?: @"";
        NSMutableArray *rows = [NSMutableArray array];
        for (NSString *line in [output componentsSeparatedByCharactersInSet:NSCharacterSet.newlineCharacterSet]) {
            if (![line hasPrefix:@"MPC_VK_DIAGNOSTIC "]) continue;
            NSData *data = [[line substringFromIndex:18] dataUsingEncoding:NSUTF8StringEncoding];
            id value = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
            if ([value isKindOfClass:NSDictionary.class]) [rows addObject:value];
        }
        NSDictionary *draw = rows.count == 1 ? rows[0] : @{};
        BOOL correct = result == 0 && rows.count == 1 && [draw[@"software"] isEqual:@NO] &&
            [draw[@"width"] intValue] == 1280 && [draw[@"height"] intValue] == 720 &&
            [draw[@"shader_phases"] intValue] == 2 && [draw[@"pixels_checked"] intValue] == 1843200 &&
            [draw[@"mismatches"] isEqual:@0] && [draw[@"channel_sum"] unsignedLongLongValue] == UINT64_C(1219256320) &&
            [draw[@"validation_errors"] isEqual:@0] && [draw[@"vendor_id"] intValue] == 0x106b &&
            [draw[@"device_type"] intValue] == 1;
        return @{@"schema": @1, @"scope": @"physical-ios-native-vulkan-offscreen-gate",
            @"status": correct ? @"passed" : @"failed", @"exit_status": @(result), @"elapsed_ms": @(elapsed),
            @"diagnostic": draw, @"payload": receipt, @"native_vulkan_to_metal_verified": @(correct),
            @"path": @"native-ios-arm64-vulkan-MoltenVK-Metal-offscreen", @"linux_graphics": @NO,
            @"presentation_verified": @NO, @"gameplay_verified": @NO, @"requires_relaunch": @(result != 0),
            @"limitation": @"Native offscreen shader/readback only, not the Linux transport or moving presentation. Validation availability is recorded. After an aborted diagnostic, close/relaunch to reclaim partial graphics resources."};
    }
}
