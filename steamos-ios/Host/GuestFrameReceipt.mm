#import "GuestFrameImport.h"
#include "../Engine/ImagePixelContract.h"
static NSArray *rows(NSString *serial, NSString *prefix) {
    NSMutableArray *result = [NSMutableArray array];
    for (NSString *line in [serial componentsSeparatedByCharactersInSet:NSCharacterSet.newlineCharacterSet]) {
        if (![line hasPrefix:prefix]) continue;
        NSData *data = [[line substringFromIndex:prefix.length] dataUsingEncoding:NSUTF8StringEncoding];
        id value = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
        [result addObject:[value isKindOfClass:NSDictionary.class] ? value : @{}];
    }
    return result;
}
NSDictionary *MPCValidateGuestFrameImport(NSString *serial, NSString *nonce, NSDictionary *native,
    BOOL engineFinished, BOOL linuxPassed, BOOL guestMetalPassed) {
    NSArray *producers = rows(serial, @"MPC_FRAME_PRODUCER ");
    NSArray *exits = rows(serial, @"MPC_FRAME_EXIT ");
    NSArray *rejected = rows(serial, @"MPC_FRAME_REJECTED ");
    NSArray *images = native[@"images"];
    BOOL passed = engineFinished && linuxPassed && guestMetalPassed &&
        [native[@"scope"] isEqual:@"native-metal-linux-eight-frame-import"] && [native[@"run"] isEqual:nonce] &&
        [native[@"errors"] isEqual:@0] && [native[@"active"] isEqual:@NO] && [native[@"reading"] isEqual:@NO] &&
        [native[@"registry_id"] unsignedLongLongValue] != 0 && [native[@"diagnostic_full_image_readbacks"] isEqual:@2] &&
        [images isKindOfClass:NSArray.class] && images.count == 8 && producers.count == 8 && exits.count == 1 && rejected.count == 0;
    NSArray *lines = [serial componentsSeparatedByCharactersInSet:NSCharacterSet.newlineCharacterSet];
    NSUInteger guestExits = 0;
    for (NSString *line in lines) if ([line isEqual:@"MPC_FRAME_GUEST_EXIT=0"]) guestExits++;
    passed = passed && guestExits == 1;
    NSDictionary *exit = exits.firstObject ?: @{};
    passed = passed && [exit[@"schema"] isEqual:@1] && [exit[@"run"] isEqual:nonce] &&
        [exit[@"status"] isEqual:@0] && [exit[@"phases"] isEqual:@8] &&
        [exit[@"scanout_disabled"] isEqual:@YES] && [exit[@"images_released"] isEqual:@YES];
    NSArray *events = native[@"events"];
    passed = passed && [events isKindOfClass:NSArray.class] && events.count >= 24 && events.count <= 64;
    BOOL active = NO;
    uint64_t sequence = 0, generation = 0, resource = 0;
    NSUInteger installs = 0;
    NSMutableSet *flushed = [NSMutableSet set];
    NSMutableDictionary *eventResources = [NSMutableDictionary dictionary];
    NSMutableDictionary *firstFlushedGeneration = [NSMutableDictionary dictionary];
    NSMutableSet *installedResources = [NSMutableSet set];
    if (![events isKindOfClass:NSArray.class]) events = @[];
    for (NSDictionary *event in events) {
        if (!passed) break;
        if (![event isKindOfClass:NSDictionary.class] ||
            [event[@"sequence"] unsignedLongLongValue] != ++sequence) { passed = NO; break; }
        unsigned kind = [event[@"kind"] unsignedIntValue];
        uint64_t g = [event[@"generation"] unsignedLongLongValue], r = [event[@"resource_id"] unsignedLongLongValue];
        if (kind == 1) {
            passed = !active && g > generation && r != 0;
            generation = g; resource = r; active = YES; installs++;
            eventResources[@(g)] = @(r);
            [installedResources addObject:@(r)];
        } else if (kind == 2) {
            passed = active && g == generation && r == resource;
            [flushed addObject:@(g)];
            if (!firstFlushedGeneration[@(r)]) firstFlushedGeneration[@(r)] = @(g);
        } else if (kind == 3) {
            passed = active && g == generation && r == resource;
            active = NO;
        } else passed = NO;
    }
    passed = passed && !active && installs >= 8 && flushed.count == installs && installedResources.count == 8;
    NSMutableSet *resources = [NSMutableSet set], *generations = [NSMutableSet set];
    uint64_t pixels = 0, sum = 0;
    for (NSUInteger i = 0; passed && i < 8; ++i) {
        NSDictionary *producer = producers[i], *image = images[i];
        if (![image isKindOfClass:NSDictionary.class]) { passed = NO; break; }
        NSNumber *phase = @(i * 17);
        id resource = producer[@"resource_id"], generation = image[@"generation"];
        if (![resource isKindOfClass:NSNumber.class] || ![generation isKindOfClass:NSNumber.class]) { passed = NO; break; }
        uint64_t offset = [producer[@"offset"] unsignedLongLongValue],
                 pitch = [producer[@"row_pitch"] unsignedLongLongValue],
                 allocation = [producer[@"allocation_bytes"] unsignedLongLongValue];
        passed = [producer[@"schema"] isEqual:@1] && [producer[@"run"] isEqual:nonce] &&
            [producer[@"tiling"] isEqual:@"drm-format-modifier"] &&
            [producer[@"drm_modifier"] isEqual:@0] && [producer[@"memory_plane"] isEqual:@0] &&
            [producer[@"vulkan_format"] isEqual:@(MPC_IMAGE_VULKAN_BGRA8)] &&
            [producer[@"drm_fourcc"] isEqual:@(MPC_IMAGE_DRM_XRGB8)] &&
            [producer[@"virtio_format"] isEqual:@(MPC_IMAGE_VIRTIO_BGRX8)] &&
            [producer[@"channel_order"] isEqual:@"bgra"] && [image[@"channel_order"] isEqual:@"bgra"] &&
            [image[@"native_pixel_format"] isEqual:@(MPC_IMAGE_METAL_BGRA8)] &&
            [image[@"virtio_format"] isEqual:producer[@"virtio_format"]] &&
            [producer[@"phase"] isEqual:phase] && [image[@"phase"] isEqual:phase] &&
            [producer[@"width"] isEqual:@1280] && [producer[@"height"] isEqual:@720] &&
            [producer[@"producer_fence_completed"] isEqual:@YES] && [producer[@"external_queue_release"] isEqual:@YES] &&
            [resource unsignedLongLongValue] != 0 && [generation unsignedLongLongValue] != 0 &&
            ![resources containsObject:resource] && ![generations containsObject:generation] &&
            [image[@"resource_id"] isEqual:resource] && [image[@"row_pitch"] isEqual:producer[@"row_pitch"]] &&
            [image[@"offset"] isEqual:producer[@"offset"]] && pitch >= 5120 && pitch <= (1u << 24) &&
            offset <= allocation && pitch * 720 <= allocation - offset &&
            [image[@"backing_bytes"] unsignedLongLongValue] >= offset + pitch * 720 &&
            [image[@"native_buffer_alias_verified"] isEqual:@YES] &&
            [image[@"native_registry_id"] isEqual:native[@"registry_id"]] &&
            [image[@"width"] isEqual:@1280] && [image[@"height"] isEqual:@720] &&
            [image[@"pixel_verification_performed"] isEqual:@(i == 0 || i == 7)] &&
            [image[@"pixels_checked"] isEqual:(i == 0 || i == 7 ? @921600 : @0)] && [image[@"mismatches"] isEqual:@0] &&
            [flushed containsObject:generation] && [eventResources[generation] isEqual:resource] &&
            [firstFlushedGeneration[resource] isEqual:generation] &&
            [image[@"channel_sum"] isEqual:(i == 0 ? @615690240 : i == 7 ? @665579520 : @0)] &&
            ((i != 0 && i != 7) || ([image[@"consumer_status"] isEqual:@4] && [image[@"consumer_error"] isEqual:@NO]));
        [resources addObject:resource]; [generations addObject:generation];
        pixels += [image[@"pixels_checked"] unsignedLongLongValue];
        sum += [image[@"channel_sum"] unsignedLongLongValue];
    }
    passed = passed && [resources isEqualToSet:installedResources] && pixels == 1843200 && sum == 1281269760;
    NSArray *renders = rows(serial, @"MPC_VK_FRAME_RENDER ");
    NSDictionary *render = renders.firstObject ?: @{};
    passed = passed && renders.count == 1 && [render[@"machine"] isEqual:@"aarch64"] && [render[@"pixels_checked"] isEqual:@7372800] &&
        [render[@"shader_phases"] isEqual:@8] && [render[@"width"] isEqual:@1280] &&
        [render[@"height"] isEqual:@720] && [render[@"mismatches"] isEqual:@0] &&
        [render[@"channel_sum"] isEqual:@5157519360ULL] && [render[@"software"] isEqual:@NO] && [render[@"validation_errors"] isEqual:@0] &&
        [render[@"device_type"] unsignedIntValue] != 4 && [render[@"device_type"] unsignedIntValue] != 0 &&
        [render[@"metal_host_verified"] isEqual:@NO] && [render[@"presentation_verified"] isEqual:@NO] &&
        [render[@"game_fps_verified"] isEqual:@NO];
    NSArray *baseDraws = rows(serial, @"MPC_VK_DIAGNOSTIC "), *caps = rows(serial, @"MPC_FRAME_CAPABILITIES ");
    NSDictionary *base = baseDraws.firstObject ?: @{}, *cap = caps.firstObject ?: @{};
    passed = passed && baseDraws.count == 1 && caps.count == 1 && [cap[@"schema"] isEqual:@1] &&
        [cap[@"run"] isEqual:nonce] && [cap[@"result"] isEqual:@0] &&
        ([cap[@"external_features"] unsignedIntValue] & 2) && ([cap[@"compatible_handles"] unsignedIntValue] & 512) &&
        [cap[@"max_width"] unsignedIntValue] >= 1280 && [cap[@"max_height"] unsignedIntValue] >= 720;
    for (NSString *key in @[@"renderer", @"api_version", @"driver_version", @"vendor_id", @"device_id", @"device_type"])
        passed = passed && render[key] && [render[key] isEqual:base[key]];
    NSArray *drmRows = rows(serial, @"MPC_FRAME_DRM_RESOURCE ");
    passed = passed && drmRows.count == 8;
    for (NSUInteger i = 0; passed && i < 8; ++i) {
        NSDictionary *drm = drmRows[i], *producer = producers[i];
        passed = [drm[@"schema"] isEqual:@1] && [drm[@"run"] isEqual:nonce] &&
            [drm[@"gem_handle"] unsignedLongLongValue] > 0 &&
            [drm[@"resource_bytes"] unsignedLongLongValue] >= [producer[@"offset"] unsignedLongLongValue] +
                [producer[@"row_pitch"] unsignedLongLongValue] * 720;
        for (NSString *key in @[@"resource_id", @"phase", @"row_pitch", @"offset"])
            passed = passed && [drm[key] isEqual:producer[key]];
    }
    return @{@"schema": @1, @"scope": @"physical-ios-linux-guest-eight-frame-import-gate", @"run": nonce,
        @"host_memory_import_verified": @(passed), @"native": native, @"guest_producers": producers,
        @"guest_exits": exits, @"guest_render": render, @"guest_rejections": rejected,
        @"reason": passed ? @"eight-fenced-linux-images-matched-native-aliases-and-two-endpoint-readbacks" : @"image-import-acceptance-incomplete",
        @"pixels_checked": @(pixels), @"channel_sum": @(sum), @"presentation_verified": @NO,
        @"zero_copy_transport_verified": @NO, @"gameplay_verified": @NO};
}
