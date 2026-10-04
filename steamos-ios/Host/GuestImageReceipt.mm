#import "GuestImageImport.h"
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
NSDictionary *MPCValidateGuestImageImport(NSString *serial, NSString *nonce, NSDictionary *native,
    BOOL engineFinished, BOOL linuxPassed, BOOL guestMetalPassed) {
    NSArray *producers = rows(serial, @"MPC_IMAGE_PRODUCER ");
    NSArray *exits = rows(serial, @"MPC_IMAGE_EXIT ");
    NSArray *rejected = rows(serial, @"MPC_IMAGE_REJECTED ");
    NSArray *images = native[@"images"];
    BOOL passed = engineFinished && linuxPassed && guestMetalPassed &&
        [native[@"scope"] isEqual:@"native-metal-linux-linear-image-import"] && [native[@"run"] isEqual:nonce] &&
        [native[@"errors"] isEqual:@0] && [native[@"active"] isEqual:@NO] && [native[@"reading"] isEqual:@NO] &&
        [native[@"registry_id"] unsignedLongLongValue] != 0 &&
        [images isKindOfClass:NSArray.class] && images.count == 2 && producers.count == 2 && exits.count == 1 && rejected.count == 0;
    NSArray *lines = [serial componentsSeparatedByCharactersInSet:NSCharacterSet.newlineCharacterSet];
    NSUInteger guestExits = 0;
    for (NSString *line in lines) if ([line isEqual:@"MPC_IMAGE_GUEST_EXIT=0"]) guestExits++;
    passed = passed && guestExits == 1;
    NSDictionary *exit = exits.firstObject ?: @{};
    passed = passed && [exit[@"schema"] isEqual:@1] && [exit[@"run"] isEqual:nonce] &&
        [exit[@"status"] isEqual:@0] && [exit[@"phases"] isEqual:@2] &&
        [exit[@"scanout_disabled"] isEqual:@YES] && [exit[@"images_released"] isEqual:@YES];
    NSArray *events = native[@"events"];
    passed = passed && [events isKindOfClass:NSArray.class] && events.count >= 6 && events.count <= 64;
    BOOL active = NO;
    uint64_t sequence = 0, generation = 0, resource = 0;
    NSUInteger installs = 0;
    NSMutableSet *flushed = [NSMutableSet set];
    NSMutableDictionary *eventResources = [NSMutableDictionary dictionary];
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
        } else if (kind == 2) {
            passed = active && g == generation && r == resource;
            [flushed addObject:@(g)];
        } else if (kind == 3) {
            passed = active && g == generation && r == resource;
            active = NO;
        } else passed = NO;
    }
    passed = passed && !active && installs == 2 && flushed.count == 2;
    NSMutableSet *resources = [NSMutableSet set], *generations = [NSMutableSet set];
    uint64_t pixels = 0, sum = 0;
    for (NSUInteger i = 0; passed && i < 2; ++i) {
        NSDictionary *producer = producers[i], *image = images[i];
        if (![image isKindOfClass:NSDictionary.class]) { passed = NO; break; }
        NSNumber *phase = i ? @41 : @0;
        id resource = producer[@"resource_id"], generation = image[@"generation"];
        if (![resource isKindOfClass:NSNumber.class] || ![generation isKindOfClass:NSNumber.class]) { passed = NO; break; }
        uint64_t offset = [producer[@"offset"] unsignedLongLongValue],
                 pitch = [producer[@"row_pitch"] unsignedLongLongValue],
                 allocation = [producer[@"allocation_bytes"] unsignedLongLongValue];
        passed = [producer[@"schema"] isEqual:@1] && [producer[@"run"] isEqual:nonce] &&
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
            [image[@"pixels_checked"] isEqual:@921600] && [image[@"mismatches"] isEqual:@0] &&
            [flushed containsObject:generation] && [eventResources[generation] isEqual:resource] &&
            [image[@"channel_sum"] isEqual:(i ? @603566080 : @615690240)] &&
            [image[@"consumer_status"] isEqual:@4] && [image[@"consumer_error"] isEqual:@NO];
        [resources addObject:resource]; [generations addObject:generation];
        pixels += [image[@"pixels_checked"] unsignedLongLongValue];
        sum += [image[@"channel_sum"] unsignedLongLongValue];
    }
    passed = passed && pixels == 1843200 && sum == 1219256320;
    return @{@"schema": @1, @"scope": @"physical-ios-linux-guest-image-import-gate", @"run": nonce,
        @"host_memory_import_verified": @(passed), @"native": native, @"guest_producers": producers,
        @"guest_exits": exits, @"guest_rejections": rejected,
        @"reason": passed ? @"two-fenced-linux-images-matched-native-metal-consumers" : @"image-import-acceptance-incomplete",
        @"pixels_checked": @(pixels), @"channel_sum": @(sum), @"presentation_verified": @NO,
        @"zero_copy_transport_verified": @NO, @"gameplay_verified": @NO};
}
