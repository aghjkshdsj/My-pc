// Fresh MIT evidence validator. Synthetic test receipts are not device proof.
#import "MovingFrameTransport.h"
#include "../Engine/MovingFrameContract.h"
#include <cmath>
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
static uint64_t expectedSum(unsigned phase) {
    uint64_t sumX = 0, sumY = 0;
    for (unsigned x = 0; x < 1280; ++x) sumX += (x + phase) & 255u;
    for (unsigned y = 0; y < 720; ++y) sumY += (y + phase) & 255u;
    return 720 * sumX + 1280 * sumY + uint64_t(1280 * 720) * ((165u ^ phase) + 255u);
}
NSDictionary *MPCValidateMovingFrames(NSString *serial, NSString *nonce, NSDictionary *native,
    NSDictionary *screen, BOOL engineFinished, BOOL linuxPassed, BOOL metalPassed) {
    NSArray *controls = rows(serial, @"MPC_MOVE_CTL "), *received = rows(serial, @"MPC_MOVE_RELEASE_RECEIVED "),
        *exits = rows(serial, @"MPC_MOVE_EXIT "), *rejected = rows(serial, @"MPC_MOVE_REJECTED "),
        *renders = rows(serial, @"MPC_VK_MOVING_RENDER "), *caps = rows(serial, @"MPC_MOVE_CAPABILITIES ");
    NSArray *buffers = native[@"buffers"], *offers = native[@"offers"], *releases = native[@"releases"],
        *acquires = native[@"reacquisitions"], *images = native[@"images"], *events = native[@"events"], *draws = screen[@"frames"];
    BOOL passed = engineFinished && linuxPassed && metalPassed && nonce.length == 32 &&
        [native[@"scope"] isEqual:@"native-explicit-linux-moving-release"] && [native[@"run"] isEqual:nonce] &&
        [native[@"errors"] isEqual:@0] && [native[@"registry_id"] unsignedLongLongValue] &&
        [native[@"finished"] isEqual:@YES] && [native[@"active"] isEqual:@NO] &&
        [native[@"ledger_drained"] isEqual:@YES] && [native[@"ledger_faulted"] isEqual:@NO] &&
        [native[@"pending_consumers"] isEqual:@0] && [native[@"reader_joined"] isEqual:@YES] &&
        [native[@"channel_eof"] isEqual:@YES] && [native[@"diagnostic_full_image_readbacks"] isEqual:@2] &&
        [native[@"binary_replies_sent"] isEqual:@364] && [native[@"final_submission_fence"] isEqual:@240] &&
        [native[@"source_release"] isEqual:@"actual-metal-gpu-terminal-callback"] &&
        [native[@"production_kms_wsi_verified"] isEqual:@NO] &&
        [screen[@"scope"] isEqual:@"native-metal-three-buffer-changing-linux-screen"] && [screen[@"run"] isEqual:nonce] &&
        [screen[@"registry_id"] isEqual:native[@"registry_id"]] && [screen[@"errors"] isEqual:@0] &&
        [screen[@"pending"] isEqual:@0] && [screen[@"interrupted"] isEqual:@NO] && [screen[@"surface_visible"] isEqual:@YES] &&
        [screen[@"maximum_inflight"] isEqual:@1] && [screen[@"drawable_limit"] isEqual:@2] &&
        [screen[@"drawable_cpu_readbacks"] isEqual:@0] && [screen[@"diagnostic_source_readbacks"] isEqual:@2];
    for (id array in @[buffers ?: @0, offers ?: @0, releases ?: @0, acquires ?: @0, images ?: @0, events ?: @0, draws ?: @0])
        passed = passed && [array isKindOfClass:NSArray.class];
    if (!passed) return @{@"schema": @1, @"scope": @"physical-ios-linux-three-buffer-moving-output", @"run": nonce,
        @"buffer_reuse_verified": @NO, @"presentation_verified": @NO, @"native": native, @"screen": screen,
        @"reason": @"moving-lifecycle-or-prerequisites-incomplete"};
    passed = buffers.count == 3 && offers.count == 120 && releases.count == 120 && acquires.count == 120 &&
        images.count == 120 && draws.count == 120 && events.count >= 360 && events.count <= 2048 &&
        controls.count == 244 && received.count == 120 && exits.count == 1 && rejected.count == 0 && renders.count == 1 && caps.count == 1;
    NSUInteger guestExits = 0;
    for (NSString *line in [serial componentsSeparatedByCharactersInSet:NSCharacterSet.newlineCharacterSet])
        if ([line isEqual:@"MPC_MOVE_GUEST_EXIT=0"]) guestExits++;
    passed = passed && guestExits == 1;
    NSDictionary *exit = exits.firstObject ?: @{}, *render = renders.firstObject ?: @{}, *cap = caps.firstObject ?: @{};
    passed = passed && [exit[@"schema"] isEqual:@1] && [exit[@"run"] isEqual:nonce] && [exit[@"status"] isEqual:@0] &&
        [exit[@"frames"] isEqual:@120] && [exit[@"buffers"] isEqual:@3] && [exit[@"scanout_disabled"] isEqual:@YES] &&
        [exit[@"images_released"] isEqual:@YES] && [render[@"machine"] isEqual:@"aarch64"] &&
        [render[@"shader_phases"] isEqual:@120] && [render[@"pixels_checked"] isEqual:@1843200] &&
        [render[@"width"] isEqual:@1280] && [render[@"height"] isEqual:@720] &&
        [render[@"mismatches"] isEqual:@0] && [render[@"validation_errors"] isEqual:@0] &&
        [render[@"software"] isEqual:@NO] && [render[@"device_type"] unsignedIntValue] != 4 &&
        [render[@"device_type"] unsignedIntValue] != 0 && [render[@"metal_host_verified"] isEqual:@NO] &&
        [render[@"presentation_verified"] isEqual:@NO] && [render[@"game_fps_verified"] isEqual:@NO] &&
        [cap[@"schema"] isEqual:@1] && [cap[@"run"] isEqual:nonce] && [cap[@"result"] isEqual:@0] &&
        [cap[@"tiling"] isEqual:@"drm-format-modifier"] && [cap[@"drm_modifier"] isEqual:@0] &&
        ([cap[@"external_features"] unsignedIntValue] & 2) && ([cap[@"compatible_handles"] unsignedIntValue] & 512) &&
        [cap[@"max_width"] unsignedIntValue] >= 1280 && [cap[@"max_height"] unsignedIntValue] >= 720;
    NSArray *baseRenders = rows(serial, @"MPC_VK_DIAGNOSTIC ");
    NSDictionary *base = baseRenders.firstObject ?: @{}; passed = passed && baseRenders.count == 1;
    for (NSString *key in @[@"renderer", @"api_version", @"driver_version", @"vendor_id", @"device_id", @"device_type"])
        passed = passed && render[key] && [render[key] isEqual:base[key]];
    // Verify the guest/host control ordering, including acquisition-before-reuse.
    NSUInteger offerIndex = 0, acquireIndex = 0, fence = 0;
    NSMutableSet *resources = [NSMutableSet set], *released = [NSMutableSet set];
    NSMutableDictionary *leased = [NSMutableDictionary dictionary];
    for (NSUInteger i = 0; passed && i < controls.count; ++i) {
        NSDictionary *row = controls[i];
        passed = [row[@"schema"] isEqual:@1] && [row[@"run"] isEqual:nonce];
        if (i < 3) {
            NSDictionary *buffer = buffers[i];
            id resource = row[@"resource_id"];
            passed = passed && [row[@"type"] isEqual:@"register"] && [row[@"slot"] isEqual:@(i)] &&
                [resource unsignedLongLongValue] && ![resources containsObject:resource] &&
                [row[@"incarnation"] isEqual:@1] && [row[@"width"] isEqual:@1280] && [row[@"height"] isEqual:@720] &&
                [row[@"format"] isEqual:@80] && [row[@"row_pitch"] unsignedLongLongValue] >= 5120 &&
                [row[@"backing_bytes"] unsignedLongLongValue] <= 64u * 1024u * 1024u;
            for (NSString *key in row) passed = passed && [buffer[key] isEqual:row[key]];
            if (resource) [resources addObject:resource];
        } else if ([row[@"type"] isEqual:@"offer"]) {
            if (offerIndex >= 120) { passed = NO; break; }
            NSDictionary *offer = offers[offerIndex]; id resource = row[@"resource_id"];
            passed = passed && [row[@"serial"] isEqual:@(offerIndex + 1)] && [row[@"incarnation"] isEqual:@1] &&
                [row[@"phase"] isEqual:@(mpc_moving_phase((unsigned)offerIndex))] &&
                [row[@"producer_fence"] isEqual:@(++fence)] && [row[@"producer_fence_completed"] isEqual:@YES] &&
                [row[@"external_queue_release"] isEqual:@YES] && [resource isEqual:buffers[offerIndex % 3][@"resource_id"]] &&
                !leased[resource] && [offer[@"native_consumed"] isEqual:@YES] && [offer[@"release_sent"] isEqual:@YES] &&
                [offer[@"terminal_status"] isEqual:@4] && [offer[@"terminal_error"] isEqual:@NO];
            for (NSString *key in row) passed = passed && [offer[key] isEqual:row[key]];
            if (resource) leased[resource] = row[@"serial"]; offerIndex++;
        } else if ([row[@"type"] isEqual:@"reacquired"]) {
            if (acquireIndex >= 120) { passed = NO; break; }
            NSDictionary *nativeAcquire = acquires[acquireIndex]; id resource = row[@"resource_id"];
            NSUInteger n = [row[@"serial"] unsignedIntegerValue];
            passed = passed && resource && n > 0 && n <= offerIndex && [row[@"incarnation"] isEqual:@1] &&
                [leased[resource] isEqual:row[@"serial"]] && ![released containsObject:row[@"serial"]] &&
                [row[@"release"] isEqual:releases[n ? n - 1 : 0][@"release"]] &&
                [row[@"acquire_fence"] isEqual:@(++fence)] && [row[@"acquire_fence_completed"] isEqual:@YES] &&
                [nativeAcquire isEqual:row];
            if (resource) [leased removeObjectForKey:resource];
            if (row[@"serial"]) [released addObject:row[@"serial"]]; acquireIndex++;
        } else {
            passed = passed && i == 243 && [row[@"type"] isEqual:@"finish"] && [row[@"frames"] isEqual:@120] &&
                [row[@"buffers"] isEqual:@3] && !leased.count;
        }
    }
    passed = passed && offerIndex == 120 && acquireIndex == 120 && released.count == 120 && fence == 240;
    // Independently join each actual install/flush generation to its source draw.
    BOOL active = NO; uint64_t sequence = 0, generation = 0, resource = 0;
    NSMutableDictionary *generationResources = [NSMutableDictionary dictionary];
    NSMutableSet *flushed = [NSMutableSet set], *imageGenerations = [NSMutableSet set], *drawables = [NSMutableSet set];
    for (NSDictionary *event in events) {
        if (!passed) break;
        uint64_t g = [event[@"generation"] unsignedLongLongValue], r = [event[@"resource_id"] unsignedLongLongValue];
        passed = [event[@"sequence"] isEqual:@(++sequence)];
        if ([event[@"kind"] isEqual:@1]) {
            passed = passed && !active && g > generation && [resources containsObject:@(r)];
            generation = g; resource = r; active = YES; generationResources[@(g)] = @(r);
        } else if ([event[@"kind"] isEqual:@2]) {
            passed = passed && active && g == generation && r == resource; [flushed addObject:@(g)];
        } else if ([event[@"kind"] isEqual:@3]) {
            passed = passed && active && g == generation && r == resource; active = NO;
        } else passed = NO;
    }
    passed = passed && !active && generationResources.count == 120 && flushed.count == 120;
    uint64_t sum = 0, pixels = 0; NSUInteger missingTimes = 0; double previousTime = 0;
    for (NSUInteger i = 0; passed && i < 120; ++i) {
        NSDictionary *image = images[i], *draw = draws[i], *release = releases[i], *guestRelease = received[i], *offer = offers[i];
        NSNumber *serialID = @(i + 1), *phase = @(mpc_moving_phase((unsigned)i));
        id r = offer[@"resource_id"], g = image[@"generation"];
        BOOL endpoint = mpc_moving_endpoint((unsigned)i);
        uint64_t offset = [image[@"offset"] unsignedLongLongValue], stride = [image[@"row_pitch"] unsignedLongLongValue],
            bytes = [image[@"backing_bytes"] unsignedLongLongValue], alignment = [image[@"linear_alignment"] unsignedLongLongValue];
        passed = !image[@"error"] && !draw[@"error"] && [image[@"serial"] isEqual:serialID] &&
            [image[@"incarnation"] isEqual:@1] && [image[@"resource_id"] isEqual:r] && [image[@"phase"] isEqual:phase] &&
            [image[@"native_registry_id"] isEqual:native[@"registry_id"]] && [image[@"native_buffer_alias_verified"] isEqual:@YES] &&
            [image[@"width"] isEqual:@1280] && [image[@"height"] isEqual:@720] && [image[@"native_pixel_format"] isEqual:@80] &&
            [image[@"virtio_format"] isEqual:@2] && [image[@"channel_order"] isEqual:@"bgra"] &&
            stride >= 5120 && stride <= (1u << 20) && alignment && !(alignment & (alignment - 1)) &&
            alignment <= 65536 && stride % alignment == 0 && offset % alignment == 0 &&
            bytes <= 64u * 1024u * 1024u && offset <= bytes && stride * 720 <= bytes - offset &&
            [image[@"row_pitch"] isEqual:buffers[i % 3][@"row_pitch"]] && [image[@"offset"] isEqual:buffers[i % 3][@"offset"]] &&
            [image[@"pixel_verification_performed"] isEqual:@(endpoint)] && [image[@"mismatches"] isEqual:@0] &&
            [image[@"pixels_checked"] isEqual:(endpoint ? @921600 : @0)] &&
            [image[@"channel_sum"] isEqual:@(endpoint ? expectedSum(phase.unsignedIntValue) : 0)] &&
            (!endpoint || ([image[@"endpoint_consumer_status"] isEqual:@4] && [image[@"endpoint_consumer_error"] isEqual:@NO])) &&
            [g unsignedLongLongValue] && ![imageGenerations containsObject:g] && [flushed containsObject:g] &&
            [generationResources[g] isEqual:r] && [offer[@"generation"] isEqual:g] &&
            [draw[@"resource_id"] isEqual:r] && [draw[@"generation"] isEqual:g] && [draw[@"phase"] isEqual:phase] &&
            [draw[@"frame_index"] isEqual:serialID] && [draw[@"source_registry_id"] isEqual:native[@"registry_id"]] &&
            [draw[@"drawable_registry_id"] isEqual:native[@"registry_id"]] && [draw[@"source_is_imported_guest_texture"] isEqual:@YES] &&
            [draw[@"source_width"] isEqual:@1280] && [draw[@"source_height"] isEqual:@720] &&
            [draw[@"source_pixel_format"] isEqual:@80] && [draw[@"drawable_pixel_format"] isEqual:@80] &&
            [draw[@"gpu_submitted"] isEqual:@YES] && [draw[@"gpu_completed"] isEqual:@YES] && [draw[@"consumer_status"] isEqual:@4] &&
            [draw[@"consumer_error"] isEqual:@NO] && [draw[@"completion_join_retired"] isEqual:@YES] &&
            [draw[@"drawable_presented"] isEqual:@YES] && ![draw[@"presentation_aborted"] boolValue] &&
            [draw[@"presents_with_transaction"] isEqual:@YES] && [draw[@"presentation_on_main_thread"] isEqual:@YES] &&
            [draw[@"presentation_application_state"] isEqual:@0] && [draw[@"presentation_call_completed"] isEqual:@YES] &&
            [draw[@"drawable_id"] isKindOfClass:NSNumber.class] && [draw[@"drawable_id"] longLongValue] >= 0 &&
            [release[@"serial"] isEqual:serialID] && [release[@"incarnation"] isEqual:@1] && [release[@"resource_id"] isEqual:r] &&
            [release[@"release"] isEqual:serialID] && [release[@"status"] isEqual:@4] && [release[@"has_error"] isEqual:@NO] &&
            [release[@"wire_sent"] isEqual:@YES] && [release[@"actual_gpu_terminal_callback"] isEqual:@YES] &&
            [release[@"registry_id"] isEqual:native[@"registry_id"]] && [guestRelease[@"schema"] isEqual:@1] &&
            [guestRelease[@"run"] isEqual:nonce] && [guestRelease[@"serial"] isEqual:serialID] &&
            [guestRelease[@"resource_id"] isEqual:r] && [guestRelease[@"incarnation"] isEqual:@1] &&
            [guestRelease[@"release"] isEqual:release[@"release"]] && [guestRelease[@"code"] isEqual:@4] &&
            [guestRelease[@"native_registry_id"] isEqual:native[@"registry_id"]];
        double start = [draw[@"gpu_start_seconds"] doubleValue], end = [draw[@"gpu_end_seconds"] doubleValue];
        passed = passed && std::isfinite(start) && std::isfinite(end) && start > 0 && end >= start;
        double shown = [draw[@"presented_seconds"] doubleValue];
        if (!std::isfinite(shown) || shown <= previousTime || shown <= 0 || shown < end) missingTimes++;
        if (std::isfinite(shown) && shown > 0) previousTime = shown;
        if (g) [imageGenerations addObject:g]; if (draw[@"drawable_id"]) [drawables addObject:draw[@"drawable_id"]];
        pixels += [image[@"pixels_checked"] unsignedLongLongValue]; sum += [image[@"channel_sum"] unsignedLongLongValue];
    }
    passed = passed && pixels == 1843200 && sum == expectedSum(0) + expectedSum(mpc_moving_phase(119)) &&
        [render[@"channel_sum"] isEqual:@(sum)];
    return @{@"schema": @1, @"scope": @"physical-ios-linux-three-buffer-moving-output", @"run": nonce,
        @"buffer_reuse_verified": @(passed), @"presentation_verified": @(passed && missingTimes == 0),
        @"reason": passed ? @"120-linux-submissions-three-buffers-native-readers-and-reacquisition-matched" : @"moving-output-evidence-incomplete",
        @"native": native, @"screen": screen, @"guest_controls": controls, @"guest_releases": received,
        @"guest_exits": exits, @"guest_rejections": rejected, @"guest_render": render,
        @"pixels_checked": @(pixels), @"channel_sum": @(sum), @"missing_or_nonmonotonic_display_timestamps": @(missingTimes),
        @"production_kms_wsi_verified": @NO, @"compositor_verified": @NO, @"frame_pacing_verified": @NO,
        @"game_fps_verified": @NO, @"gameplay_verified": @NO, @"steady_state_full_image_readbacks": @0};
}
