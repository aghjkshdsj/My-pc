#import "GuestFrameImport.h"
#include <cmath>
static BOOL positive(id value) {
    return [value isKindOfClass:NSNumber.class] && std::isfinite([value doubleValue]) && [value doubleValue] > 0;
}
NSDictionary *MPCValidateGuestFrameScreen(NSString *nonce, NSDictionary *imageImport,
                                   NSDictionary *native, BOOL engineFinished) {
    NSArray *images = imageImport[@"native"][@"images"], *frames = native[@"frames"];
    BOOL passed = engineFinished && [imageImport[@"host_memory_import_verified"] isEqual:@YES] &&
        [imageImport[@"run"] isEqual:nonce] && [native[@"schema"] isEqual:@2] &&
        [native[@"scope"] isEqual:@"native-metal-eight-linux-frame-screen"] && [native[@"run"] isEqual:nonce] &&
        [native[@"registry_id"] isEqual:imageImport[@"native"][@"registry_id"]] &&
        [native[@"registry_id"] unsignedLongLongValue] > 0 &&
        [native[@"errors"] isEqual:@0] && [native[@"pending"] isEqual:@0] &&
        [native[@"interrupted"] isEqual:@NO] && [native[@"surface_visible"] isEqual:@YES] &&
        [native[@"maximum_inflight"] isEqual:@1] && [native[@"drawable_limit"] isEqual:@2] &&
        [native[@"diagnostic_source_readbacks"] isEqual:@2] && [native[@"drawable_cpu_readbacks"] isEqual:@0] &&
        [frames isKindOfClass:NSArray.class] && frames.count == 8 &&
        [images isKindOfClass:NSArray.class] && images.count == 8;
    for (NSString *key in @[@"continuous_animation_verified", @"frame_pacing_verified", @"zero_copy_transport_verified", @"gameplay_verified"])
        passed = passed && [native[key] isEqual:@NO];
    BOOL transaction = [native[@"schema"] isEqual:@2];
    if (transaction) {
        NSArray *events = native[@"lifecycle_events"];
        passed = passed && [native[@"presentation_route"] isEqual:@"scheduled-main-thread-core-animation-transaction"] &&
            [events isKindOfClass:NSArray.class] && events.count <= 32;
        double previous = 0;
        if ([events isKindOfClass:NSArray.class]) for (NSDictionary *event in events) {
            passed = passed && [event isKindOfClass:NSDictionary.class];
            if (!passed) break;
            passed = [event[@"reason"] isKindOfClass:NSString.class] && [event[@"reason"] length] > 0 &&
                [event[@"interrupts_acceptance"] isEqual:@NO] && positive(event[@"host_seconds"]) &&
                [event[@"host_seconds"] doubleValue] >= previous;
            previous = [event[@"host_seconds"] doubleValue];
        }
    }
    double previousPresented = 0; BOOL timing = YES;
    NSMutableSet *resources = [NSMutableSet set], *generations = [NSMutableSet set];
    for (NSUInteger i = 0; passed && i < 8; ++i) {
        NSDictionary *frame = frames[i], *image = images[i];
        if (![frame isKindOfClass:NSDictionary.class] || ![image isKindOfClass:NSDictionary.class]) { passed = NO; break; }
        for (NSString *key in @[@"resource_id", @"generation", @"phase"])
            passed = passed && [frame[key] isEqual:image[key]];
        passed = passed && positive(frame[@"resource_id"]) && positive(frame[@"generation"]) &&
            ![resources containsObject:frame[@"resource_id"]] && ![generations containsObject:frame[@"generation"]];
        passed = passed && [frame[@"frame_index"] isEqual:@(i + 1)] && [frame[@"phase"] isEqual:@(i * 17)] &&
            [frame[@"source_registry_id"] isEqual:native[@"registry_id"]] &&
            [frame[@"drawable_registry_id"] isEqual:native[@"registry_id"]] &&
            [frame[@"source_is_imported_guest_texture"] isEqual:@YES] &&
            [frame[@"source_width"] isEqual:@1280] && [frame[@"source_height"] isEqual:@720] &&
            [frame[@"source_pixel_format"] isEqual:@80] && [frame[@"drawable_pixel_format"] isEqual:@80] &&
            [frame[@"geometry"] isEqual:native[@"surface_geometry"]] &&
            [frame[@"gpu_completed"] isEqual:@YES] && [frame[@"drawable_presented"] isEqual:@YES] &&
            [frame[@"consumer_status"] isEqual:@4] && [frame[@"consumer_error"] isEqual:@NO] && !frame[@"error"] &&
            positive(frame[@"drawable_width"]) && positive(frame[@"drawable_height"]) &&
            [frame[@"drawable_id"] isKindOfClass:NSNumber.class] &&
            positive(frame[@"submit_seconds"]) && positive(frame[@"gpu_start_seconds"]) &&
            positive(frame[@"gpu_end_seconds"]) &&
            [frame[@"gpu_start_seconds"] doubleValue] >= [frame[@"submit_seconds"] doubleValue] &&
            [frame[@"gpu_end_seconds"] doubleValue] >= [frame[@"gpu_start_seconds"] doubleValue];
        id display = frame[@"presented_seconds"];
        passed = passed && [display isKindOfClass:NSNumber.class] && std::isfinite([display doubleValue]) && [display doubleValue] >= 0;
        timing = timing && positive(display) && [display doubleValue] >= [frame[@"gpu_end_seconds"] doubleValue] && [display doubleValue] > previousPresented;
        NSArray *v = frame[@"viewport"];
        double w = [frame[@"drawable_width"] doubleValue], h = [frame[@"drawable_height"] doubleValue];
        double scale = fmin(w / 1280, h / 720);
        double expected[] = {(w-1280*scale)/2, (h-720*scale)/2, 1280*scale, 720*scale};
        passed = passed && [v isKindOfClass:NSArray.class] && v.count == 4;
        for (NSUInteger j = 0; passed && j < 4; ++j)
            passed = [v[j] isKindOfClass:NSNumber.class] && std::isfinite([v[j] doubleValue]) &&
                     fabs([v[j] doubleValue] - expected[j]) < 0.01;
        if (transaction) {
            passed = passed && [frame[@"presents_with_transaction"] isEqual:@YES] &&
                [frame[@"presentation_on_main_thread"] isEqual:@YES] && [frame[@"presentation_application_state"] isEqual:@0] &&
                [frame[@"presentation_call_completed"] isEqual:@YES] && [frame[@"completion_join_retired"] isEqual:@YES] &&
                (![frame objectForKey:@"presentation_aborted"] || [frame[@"presentation_aborted"] isEqual:@NO]) &&
                ([frame[@"scheduled_status"] isEqual:@3] || [frame[@"scheduled_status"] isEqual:@4]) &&
                positive(frame[@"scheduled_callback_seconds"]) && positive(frame[@"presentation_enqueued_seconds"]) &&
                positive(frame[@"presented_callback_seconds"]) &&
                [frame[@"scheduled_callback_seconds"] doubleValue] >= [frame[@"submit_seconds"] doubleValue] &&
                [frame[@"presentation_enqueued_seconds"] doubleValue] >= [frame[@"scheduled_callback_seconds"] doubleValue] &&
                [frame[@"presented_callback_seconds"] doubleValue] >= [frame[@"gpu_end_seconds"] doubleValue] &&
                [frame[@"presented_callback_seconds"] doubleValue] >= [frame[@"presentation_enqueued_seconds"] doubleValue];
            timing = timing && [frame[@"presented_seconds"] doubleValue] >= [frame[@"presentation_enqueued_seconds"] doubleValue] &&
                [frame[@"presented_callback_seconds"] doubleValue] >= [frame[@"presented_seconds"] doubleValue];
        }
        previousPresented = [frame[@"presented_seconds"] doubleValue];
        if (frame[@"resource_id"]) [resources addObject:frame[@"resource_id"]];
        if (frame[@"generation"]) [generations addObject:frame[@"generation"]];
    }
    return @{@"schema": @1, @"scope": @"physical-ios-linux-eight-frame-screen-gate", @"run": nonce,
        @"gpu_sequence_verified": @(passed), @"presentation_verified": @(passed && timing), @"native": native,
        @"reason": passed ? (timing ? @"eight-linux-frames-completed-with-display-timestamps" : @"eight-linux-screen-draws-completed-display-timing-incomplete") : @"eight-frame-gpu-acceptance-incomplete",
        @"continuous_animation_verified": @NO, @"frame_pacing_verified": @NO,
        @"zero_copy_transport_verified": @NO, @"gameplay_verified": @NO};
}
