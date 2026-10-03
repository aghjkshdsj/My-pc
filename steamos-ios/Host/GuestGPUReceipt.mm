#import "ProbeBridge.h"

// Pure guest evidence checks; no renderer, hardware or presentation is mocked.
NSDictionary *MPCParseGuestGPUReceipt(NSString *text, NSString *nonce, BOOL linuxPassed) {
    NSMutableDictionary *run = [NSMutableDictionary dictionary];
    NSMutableArray<NSDictionary *> *devices = [NSMutableArray array];
    NSMutableArray<NSDictionary *> *draws = [NSMutableArray array];
    NSInteger startLine = -1, drawLine = -1, exitLine = -1;
    NSUInteger starts = 0, exits = 0;
    BOOL validStart = NO, validExit = NO;
    NSArray<NSString *> *lines = [text componentsSeparatedByCharactersInSet:NSCharacterSet.newlineCharacterSet];
    for (NSUInteger index = 0; index < lines.count; ++index) {
        NSString *line = lines[index];
        if ([line hasPrefix:@"MPC_GPU_GUEST_RUN="]) {
            starts++; startLine = static_cast<NSInteger>(index);
            validStart = [line isEqual:[@"MPC_GPU_GUEST_RUN=" stringByAppendingString:nonce]];
        }
        if ([line hasPrefix:@"MPC_GPU_GUEST_EXIT="]) {
            exits++; exitLine = static_cast<NSInteger>(index);
            validExit = [line isEqual:@"MPC_GPU_GUEST_EXIT=0"];
        }
        NSString *marker = [line hasPrefix:@"MPC_GPU_KERNEL "] ? @"MPC_GPU_KERNEL " :
            [line hasPrefix:@"MPC_VK_DIAGNOSTIC "] ? @"MPC_VK_DIAGNOSTIC " : nil;
        if (!marker) continue;
        NSData *json = [[line substringFromIndex:marker.length] dataUsingEncoding:NSUTF8StringEncoding];
        id row = [NSJSONSerialization JSONObjectWithData:json options:0 error:nil];
        NSDictionary *parsed = [row isKindOfClass:NSDictionary.class] ? row : @{@"malformed": @YES};
        if ([marker isEqual:@"MPC_GPU_KERNEL "]) [devices addObject:parsed];
        else { [draws addObject:parsed]; drawLine = static_cast<NSInteger>(index); }
    }
    NSDictionary *device = devices.firstObject ?: @{};
    NSDictionary *draw = draws.firstObject ?: @{};
    BOOL detected = devices.count == 1 && [device[@"run"] isEqual:nonce] &&
        [device[@"driver"] isEqual:@"virtio_gpu"] && [device[@"page_bytes"] isEqual:@4096];
    id parameters = device[@"parameters"];
    if (![parameters isKindOfClass:NSDictionary.class]) detected = NO;
    else for (NSString *key in @[@"1", @"3", @"4", @"6"]) {
        id parameter = parameters[key];
        detected = detected && [parameter isKindOfClass:NSDictionary.class] &&
            [parameter[@"supported"] isEqual:@YES] && [parameter[@"value"] isEqual:@1];
    }
    BOOL nonceBound = starts == 1 && exits == 1 && validStart && validExit && startLine < drawLine && drawLine < exitLine;
    BOOL pixels = linuxPassed && detected && nonceBound && draws.count == 1 &&
        [draw[@"machine"] isEqual:@"aarch64"] && [draw[@"software"] isEqual:@NO] &&
        [draw[@"width"] isEqual:@1280] && [draw[@"height"] isEqual:@720] &&
        [draw[@"shader_phases"] isEqual:@2] && [draw[@"pixels_checked"] isEqual:@1843200] &&
        [draw[@"mismatches"] isEqual:@0] && [draw[@"channel_sum"] isEqual:@1219256320LL] &&
        [draw[@"validation_errors"] isEqual:@0] && [draw[@"metal_host_verified"] isEqual:@NO] &&
        [draw[@"presentation_verified"] isEqual:@NO] && [draw[@"game_fps_verified"] isEqual:@NO];
    run[@"graphics_kernel"] = device;
    run[@"guest_vulkan"] = draw;
    run[@"fresh_guest_vulkan_nonce_bound"] = @(nonceBound);
    run[@"graphics_kernel_device_detected"] = @(detected);
    run[@"guest_vulkan_pixels_verified"] = @(pixels);
    run[@"graphics_tested"] = @(starts > 0);
    // Guest pixels and the compiled/requested route do not independently
    // attest host Metal command completion, zero-copy or presentation.
    run[@"metal_host_verified"] = @NO;
    run[@"host_memory_import_verified"] = @NO;
    return run;
}
