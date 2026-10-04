#import "GuestScreenPresentation.h"
#include <cmath>
static BOOL positive(id value) {
    return [value isKindOfClass:NSNumber.class] && std::isfinite([value doubleValue]) && [value doubleValue] > 0;
}
NSDictionary *MPCValidateGuestScreen(NSString *nonce, NSDictionary *imageImport,
                                   NSDictionary *native, BOOL engineFinished) {
    NSArray *images = imageImport[@"native"][@"images"], *frames = native[@"frames"];
    BOOL passed = engineFinished && [imageImport[@"host_memory_import_verified"] isEqual:@YES] &&
        [imageImport[@"run"] isEqual:nonce] && [native[@"schema"] isEqual:@1] &&
        [native[@"scope"] isEqual:@"native-metal-two-linux-image-screen"] && [native[@"run"] isEqual:nonce] &&
        [native[@"registry_id"] isEqual:imageImport[@"native"][@"registry_id"]] &&
        [native[@"registry_id"] unsignedLongLongValue] > 0 &&
        [native[@"errors"] isEqual:@0] && [native[@"pending"] isEqual:@0] &&
        [native[@"interrupted"] isEqual:@NO] && [native[@"surface_visible"] isEqual:@YES] &&
        [native[@"maximum_inflight"] isEqual:@1] && [native[@"drawable_limit"] isEqual:@2] &&
        [native[@"diagnostic_source_readbacks"] isEqual:@2] && [native[@"drawable_cpu_readbacks"] isEqual:@0] &&
        [frames isKindOfClass:NSArray.class] && frames.count == 2 &&
        [images isKindOfClass:NSArray.class] && images.count == 2;
    for (NSString *key in @[@"continuous_animation_verified", @"frame_pacing_verified", @"zero_copy_transport_verified", @"gameplay_verified"])
        passed = passed && [native[key] isEqual:@NO];
    double previousPresented = 0;
    NSMutableSet *resources = [NSMutableSet set], *generations = [NSMutableSet set];
    for (NSUInteger i = 0; passed && i < 2; ++i) {
        NSDictionary *frame = frames[i], *image = images[i];
        if (![frame isKindOfClass:NSDictionary.class] || ![image isKindOfClass:NSDictionary.class]) { passed = NO; break; }
        for (NSString *key in @[@"resource_id", @"generation", @"phase"])
            passed = passed && [frame[key] isEqual:image[key]];
        passed = passed && positive(frame[@"resource_id"]) && positive(frame[@"generation"]) &&
            ![resources containsObject:frame[@"resource_id"]] && ![generations containsObject:frame[@"generation"]];
        passed = passed && [frame[@"frame_index"] isEqual:@(i + 1)] && [frame[@"phase"] isEqual:(i ? @41 : @0)] &&
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
            positive(frame[@"gpu_end_seconds"]) && positive(frame[@"presented_seconds"]) &&
            [frame[@"gpu_start_seconds"] doubleValue] >= [frame[@"submit_seconds"] doubleValue] &&
            [frame[@"gpu_end_seconds"] doubleValue] >= [frame[@"gpu_start_seconds"] doubleValue] &&
            [frame[@"presented_seconds"] doubleValue] >= [frame[@"gpu_end_seconds"] doubleValue] &&
            [frame[@"presented_seconds"] doubleValue] > previousPresented;
        NSArray *v = frame[@"viewport"];
        double w = [frame[@"drawable_width"] doubleValue], h = [frame[@"drawable_height"] doubleValue];
        double scale = fmin(w / 1280, h / 720);
        double expected[] = {(w-1280*scale)/2, (h-720*scale)/2, 1280*scale, 720*scale};
        passed = passed && [v isKindOfClass:NSArray.class] && v.count == 4;
        for (NSUInteger j = 0; passed && j < 4; ++j)
            passed = [v[j] isKindOfClass:NSNumber.class] && std::isfinite([v[j] doubleValue]) &&
                     fabs([v[j] doubleValue] - expected[j]) < 0.01;
        previousPresented = [frame[@"presented_seconds"] doubleValue];
        if (frame[@"resource_id"]) [resources addObject:frame[@"resource_id"]];
        if (frame[@"generation"]) [generations addObject:frame[@"generation"]];
    }
    return @{@"schema": @1, @"scope": @"physical-ios-linux-two-image-screen-gate", @"run": nonce,
        @"presentation_verified": @(passed), @"native": native,
        @"reason": passed ? @"two-imported-linux-images-completed-and-presented" : @"screen-presentation-acceptance-incomplete",
        @"continuous_animation_verified": @NO, @"frame_pacing_verified": @NO,
        @"zero_copy_transport_verified": @NO, @"gameplay_verified": @NO};
}
