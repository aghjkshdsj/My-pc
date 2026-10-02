#import "ProbeBridge.h"
#include <CommonCrypto/CommonDigest.h>
#include <dlfcn.h>
#include <mach-o/loader.h>
#include <mach/machine.h>
#include <string.h>

extern "C" int MPCNativeVulkanDraw(void *, const char *, const char *, const char *);
static NSString *digest(NSData *data) {
    unsigned char value[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(data.bytes, static_cast<CC_LONG>(data.length), value);
    NSMutableString *text = [NSMutableString string];
    for (unsigned char byte : value) [text appendFormat:@"%02x", byte];
    return text;
}
static NSDictionary *textSection(NSData *data) {
    if (data.length < sizeof(mach_header_64)) return nil;
    const auto *header = static_cast<const mach_header_64 *>(data.bytes);
    if (header->magic != MH_MAGIC_64 || header->cputype != CPU_TYPE_ARM64 || header->filetype != MH_DYLIB ||
        header->ncmds > 1024 || sizeof(*header) + static_cast<uint64_t>(header->sizeofcmds) > data.length) return nil;
    const auto *bytes = static_cast<const uint8_t *>(data.bytes);
    uint64_t cursor = sizeof(*header), end = cursor + header->sizeofcmds;
    NSDictionary *found = nil;
    BOOL ios = NO;
    for (uint32_t i = 0; i < header->ncmds; ++i) {
        if (cursor + sizeof(load_command) > end) return nil;
        const auto *command = reinterpret_cast<const load_command *>(bytes + cursor);
        if (command->cmdsize < sizeof(load_command) || cursor + command->cmdsize > end) return nil;
        if (command->cmd == LC_BUILD_VERSION) {
            if (command->cmdsize < sizeof(build_version_command)) return nil;
            ios = reinterpret_cast<const build_version_command *>(command)->platform == 2;
        }
        if (command->cmd == LC_SEGMENT_64) {
            if (command->cmdsize < sizeof(segment_command_64)) return nil;
            const auto *segment = reinterpret_cast<const segment_command_64 *>(command);
            if (segment->nsects > 1024 || sizeof(*segment) + static_cast<uint64_t>(segment->nsects) * sizeof(section_64) > command->cmdsize) return nil;
            const auto *sections = reinterpret_cast<const section_64 *>(bytes + cursor + sizeof(*segment));
            for (uint32_t index = 0; index < segment->nsects; ++index) {
                const auto &section = sections[index];
                if (strncmp(section.sectname, "__text", 16) || strncmp(section.segname, "__TEXT", 16)) continue;
                if (found || !section.size || section.offset < end || section.size > data.length || section.offset > data.length - section.size) return nil;
                NSData *code = [data subdataWithRange:NSMakeRange(section.offset, static_cast<NSUInteger>(section.size))];
                found = @{@"bytes": @(section.size), @"sha256": digest(code)};
            }
        }
        cursor += command->cmdsize;
    }
    return ios ? found : nil;
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
        NSData *engine = [NSData dataWithContentsOfFile:framework options:NSDataReadingMappedIfSafe error:nil];
        NSDictionary *engineCode = engine ? textSection(engine) : nil;
        if (!engineCode || ![engineCode isEqual:receipt[@"engine_text_section"]])
            return @{@"status": @"failed", @"stage": @"engine-text-sha256", @"linux_graphics": @NO};
        // iLoader changes Mach-O signature/load-command data when signing.
        // Verify immutable executable bytes; retain full original hash as provenance.
        for (NSString *name in @[@"vertex.spv", @"fragment.spv"]) {
            NSString *path = [payload stringByAppendingPathComponent:name];
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
        NSString *drawReceipt = [diagnosticDirectory stringByAppendingPathComponent:@"vulkan-diagnostic.json"];
        MPCDiagnosticStage(@"native-vulkan-before-two-shader-draws", @{});
        double start = NSProcessInfo.processInfo.systemUptime;
        int result = MPCNativeVulkanDraw(library, vertex.fileSystemRepresentation, fragment.fileSystemRepresentation,
            drawReceipt.fileSystemRepresentation);
        double elapsed = (NSProcessInfo.processInfo.systemUptime - start) * 1000;
        MPCDiagnosticStage(@"native-vulkan-draw-returned", @{@"exit_status": @(result)});
        // The receipt is independent of mixed engine stdout/stderr and its encoding.
        NSData *receiptData = [NSData dataWithContentsOfFile:drawReceipt];
        NSError *parseError = nil;
        id parsed = receiptData.length && receiptData.length <= 1024 * 1024
            ? [NSJSONSerialization JSONObjectWithData:receiptData options:0 error:&parseError] : nil;
        NSDictionary *draw = [parsed isKindOfClass:NSDictionary.class] ? parsed : @{};
        NSData *output = [NSData dataWithContentsOfFile:[diagnosticDirectory stringByAppendingPathComponent:@"engine-output.log"]];
        NSData *tail = output.length > 16384 ? [output subdataWithRange:NSMakeRange(output.length - 16384, 16384)] : output;
        NSString *outputTail = tail ? [[NSString alloc] initWithData:tail encoding:NSUTF8StringEncoding] : nil;
        if (!outputTail && tail) outputTail = [[NSString alloc] initWithData:tail encoding:NSISOLatin1StringEncoding];
        BOOL correct = result == 0 && draw.count && [draw[@"software"] isEqual:@NO] &&
            [draw[@"width"] intValue] == 1280 && [draw[@"height"] intValue] == 720 &&
            [draw[@"shader_phases"] intValue] == 2 && [draw[@"pixels_checked"] intValue] == 1843200 &&
            [draw[@"mismatches"] isEqual:@0] && [draw[@"channel_sum"] unsignedLongLongValue] == UINT64_C(1219256320) &&
            [draw[@"validation_errors"] isEqual:@0] && [draw[@"vendor_id"] intValue] == 0x106b &&
            [draw[@"device_type"] intValue] == 1;
        NSString *stage = result ? @"native-draw-error" : !draw.count ? @"diagnostic-receipt-unavailable"
            : correct ? @"native-vulkan-verified" : @"diagnostic-validation";
        MPCDiagnosticStage(@"native-vulkan-receipt-checked", @{@"stage": stage, @"receipt_bytes": @(receiptData.length)});
        return @{@"schema": @1, @"scope": @"physical-ios-native-vulkan-offscreen-gate",
            @"status": correct ? @"passed" : @"failed", @"exit_status": @(result), @"elapsed_ms": @(elapsed),
            @"stage": stage, @"diagnostic_source": @"dedicated-fsynced-json-receipt",
            @"diagnostic_receipt_bytes": @(receiptData.length),
            @"diagnostic_parse_error": parseError.localizedDescription ?: @"",
            @"engine_output_tail": outputTail ?: @"",
            @"diagnostic": draw, @"payload": receipt, @"native_vulkan_to_metal_verified": @(correct),
            @"engine_text_section": engineCode, @"engine_text_section_matches": @YES,
            @"observed_signed_framework_sha256": digest(engine),
            @"path": @"native-ios-arm64-vulkan-MoltenVK-Metal-offscreen", @"linux_graphics": @NO,
            @"presentation_verified": @NO, @"gameplay_verified": @NO, @"requires_relaunch": @(result != 0),
            @"limitation": @"Native offscreen shader/readback only, not the Linux transport or moving presentation. Validation availability is recorded. After an aborted diagnostic, close/relaunch to reclaim partial graphics resources."};
    }
}
