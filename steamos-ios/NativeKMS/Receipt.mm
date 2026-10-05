/* SPDX-License-Identifier: MIT */
#import "Bridge.h"
static NSArray *rows(NSString *text,NSString *prefix) {
    NSMutableArray *result=[NSMutableArray array];
    for(NSString *line in [text componentsSeparatedByCharactersInSet:NSCharacterSet.newlineCharacterSet]) {
        if(![line hasPrefix:prefix])continue;
        NSData *data=[[line substringFromIndex:prefix.length] dataUsingEncoding:NSUTF8StringEncoding];
        id row=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
        [result addObject:[row isKindOfClass:NSDictionary.class]?row:@{}];
    }
    return result;
}
NSDictionary *MPCNativeKMSReceipt(NSString *text,NSString *nonce,NSDictionary *native,BOOL retired) {
    NSArray *abi=rows(text,@"MPC_LINUX_ABI "),*producer=rows(text,@"MPC_NATIVE_KMS_PRODUCER ");
    NSArray *flips=rows(text,@"MPC_NATIVE_KMS_FLIP "),*exit=rows(text,@"MPC_NATIVE_KMS_EXIT ");
    NSArray *render=rows(text,@"MPC_VK_NATIVE_KMS_RENDER ");
    NSArray *terminals=[native[@"recent_terminals"] isKindOfClass:NSArray.class]?native[@"recent_terminals"]:@[];
    BOOL linux=retired && abi.count==1;
    NSDictionary *a=abi.firstObject?:@{};
    linux=linux && [a[@"run"] isEqual:nonce] && [a[@"machine"] isEqual:@"aarch64"] &&
        [a[@"elf_arch"] isEqual:@"aarch64"] && [a[@"page_bytes"] isEqual:@4096] &&
        [a[@"failures"] isEqual:@0] && [a[@"checksum"] isEqual:@"1d250c45a7bbc87e"];
    for(NSString *key in @[@"signals",@"mmap_protection",@"pthread_tls_futex",@"fork_exec"])
        linux=linux && [a[key] isEqual:@YES];
    BOOL valid=linux && producer.count==8 && flips.count==8 && exit.count==1 && render.count==1 && terminals.count==8;
    for(NSString *key in @[@"actual_gpu_errors",@"canceled_before_submission",@"rejected_events",@"invalid_completions",
        @"pending_readers",@"completion_callbacks_in_progress",@"retained_backing_bytes",@"installed_images"])
        valid=valid && [native[key] isEqual:@0];
    valid=valid && [native[@"configured"] isEqual:@YES] && [native[@"accepted_readers"] isEqual:@8] &&
        [native[@"actual_gpu_completed"] isEqual:@8];
    NSMutableSet *resources=[NSMutableSet set],*tickets=[NSMutableSet set],*generations=[NSMutableSet set];
    NSNumber *session=nil,*crtc=nil;
    for(NSUInteger i=0;i<producer.count;i++) {
        NSDictionary *p=producer[i];
        valid=valid && [p[@"schema"] isEqual:@1] && [p[@"run"] isEqual:nonce] &&
            [p[@"phase"] isEqual:@(i*17)] && [p[@"width"] isEqual:@1280] && [p[@"height"] isEqual:@720] &&
            [p[@"producer_fence_completed"] isEqual:@YES] && [p[@"external_queue_release"] isEqual:@YES] &&
            [p[@"vulkan_format"] isEqual:@44] && [p[@"drm_fourcc"] isEqual:@875713112] &&
            [p[@"virtio_format"] isEqual:@2] && [p[@"drm_modifier"] isEqual:@0] && [p[@"memory_plane"] isEqual:@0] &&
            [p[@"tiling"] isEqual:@"drm-format-modifier"] && [p[@"channel_order"] isEqual:@"bgra"];
        id resource=p[@"resource_id"];
        valid=valid && [resource isKindOfClass:NSNumber.class] && [resource unsignedIntValue]>0 && ![resources containsObject:resource];
        if(resource)[resources addObject:resource];
        NSArray *matches=[terminals filteredArrayUsingPredicate:[NSPredicate predicateWithBlock:^BOOL(NSDictionary *t, NSDictionary *bindings) {
            (void)bindings;return [t[@"resource_id"] isEqual:resource];
        }]];
        if(i>=flips.count || matches.count!=1){valid=NO;continue;}
        NSDictionary *f=flips[i],*t=matches[0];
        if(!crtc)crtc=f[@"crtc"];
        if(!session)session=t[@"session"];
        valid=valid && [f[@"schema"] isEqual:@1] && [f[@"run"] isEqual:nonce] && [f[@"index"] isEqual:@(i)] &&
            [f[@"crtc"] unsignedIntValue]>0 && [f[@"crtc"] isEqual:crtc] && [f[@"framebuffer"] unsignedIntValue]>0 &&
            [f[@"event_count"] isEqual:@(i?1:0)] && [f[@"output_fence_status"] isEqual:@1] && [f[@"uart_release_used"] isEqual:@NO] &&
            [t[@"resource_id"] isEqual:resource] && [t[@"session"] unsignedLongLongValue]>0 && [t[@"session"] isEqual:session] &&
            [t[@"command"] unsignedLongLongValue]>0 && [t[@"reader"] unsignedLongLongValue]>0 && [t[@"generation"] unsignedLongLongValue]>0 &&
            [t[@"actual_metal_status"] isEqual:@4] && [t[@"actual_metal_error_code"] isEqual:@0] &&
            [t[@"gpu_command_submitted"] isEqual:@YES] && [t[@"engine_terminal_accepted"] isEqual:@YES];
        NSString *ticket=[NSString stringWithFormat:@"%@:%@:%@",t[@"session"],t[@"command"],t[@"reader"]];
        valid=valid && ![tickets containsObject:ticket] && t[@"generation"] && ![generations containsObject:t[@"generation"]];
        [tickets addObject:ticket];if(t[@"generation"])[generations addObject:t[@"generation"]];
    }
    NSDictionary *e=exit.firstObject?:@{},*r=render.firstObject?:@{};
    valid=valid && [e[@"run"] isEqual:nonce] && [e[@"status"] isEqual:@0] && [e[@"phases"] isEqual:@8] &&
        [e[@"scanout_disabled"] isEqual:@YES] && [e[@"images_released"] isEqual:@YES] &&
        [r[@"machine"] isEqual:@"aarch64"] && [r[@"software"] isEqual:@NO] &&
        [r[@"width"] isEqual:@1280] && [r[@"height"] isEqual:@720] && [r[@"shader_phases"] isEqual:@8] &&
        [r[@"pixels_checked"] isEqual:@7372800] && [r[@"mismatches"] isEqual:@0] &&
        [r[@"channel_sum"] isEqual:@5157519360ULL] && [r[@"validation_enabled"] isEqual:@YES] &&
        [r[@"synchronization_validation_requested"] isEqual:@YES] && [r[@"validation_errors"] isEqual:@0];
    NSArray *lines=[text componentsSeparatedByCharactersInSet:NSCharacterSet.newlineCharacterSet];
    for(NSString *line in @[@"MPC_LINUX_EXIT=0",@"MPC_GPU_KERNEL_EXIT=0",@"MPC_GPU_GUEST_EXIT=0",@"MPC_NATIVE_KMS_GUEST_EXIT=0"])
        valid=valid && [[lines filteredArrayUsingPredicate:[NSPredicate predicateWithFormat:@"SELF == %@",line]] count]==1;
    valid=valid && ![text containsString:@"MPC_NATIVE_KMS_REJECTED "] && ![text containsString:@"MPC_NATIVE_KMS_HELD "];
    return @{@"scope":@"standard-linux-kms-native-metal-completion-join",@"linux_execution":@(linux),
        @"standard_kms_native_completion_verified":@(valid),@"producer":producer,@"flips":flips,@"guest_render":render,
        @"cleanup":exit,@"native":native,@"desktop_verified":@NO,@"steam_verified":@NO,@"gameplay_verified":@NO,
        @"display_timing_verified":@NO,@"game_fps_verified":@NO};
}
