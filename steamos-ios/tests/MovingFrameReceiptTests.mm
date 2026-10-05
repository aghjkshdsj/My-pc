#import "MovingFrameTransport.h"
#include <cstdio>
static unsigned checks;
static NSMutableDictionary *clone(NSDictionary *input) {
    NSData *data = [NSJSONSerialization dataWithJSONObject:input options:0 error:nil];
    return [NSJSONSerialization JSONObjectWithData:data options:NSJSONReadingMutableContainers error:nil];
}
static NSDictionary *validate(NSDictionary *f, BOOL engine = YES, BOOL linux = YES, BOOL metal = YES) {
    return MPCValidateMovingFrames(f[@"serial"], f[@"nonce"], f[@"native"], f[@"screen"], engine, linux, metal);
}
static void check(BOOL condition) { checks++; if (!condition) { fprintf(stderr,"Moving receipt check %u failed\n",checks); abort(); } }
int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc != 2) return 2;
        NSDictionary *f = [NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[1])] options:0 error:nil];
        check([validate(f)[@"buffer_reuse_verified"] boolValue]); check([validate(f)[@"presentation_verified"] boolValue]);
        check(![validate(f, NO)[@"buffer_reuse_verified"] boolValue]);
        check(![validate(f, YES, NO)[@"buffer_reuse_verified"] boolValue]);
        check(![validate(f, YES, YES, NO)[@"buffer_reuse_verified"] boolValue]);
        for (NSString *key in @[@"errors", @"registry_id", @"finished", @"active", @"ledger_drained", @"ledger_faulted",
            @"pending_consumers", @"reader_joined", @"channel_eof", @"diagnostic_full_image_readbacks", @"binary_replies_sent", @"final_submission_fence"]) {
            NSMutableDictionary *bad = clone(f); [bad[@"native"] removeObjectForKey:key];
            check(![validate(bad)[@"buffer_reuse_verified"] boolValue]);
        }
        for (NSString *key in @[@"serial", @"incarnation", @"resource_id", @"phase", @"generation", @"producer_fence", @"producer_fence_completed", @"external_queue_release", @"native_consumed", @"release_sent", @"terminal_status"] ) {
            NSMutableDictionary *bad = clone(f); [bad[@"native"][@"offers"][17] removeObjectForKey:key];
            check(![validate(bad)[@"buffer_reuse_verified"] boolValue]);
        }
        for (NSString *key in @[@"resource_id", @"serial", @"incarnation", @"release", @"acquire_fence", @"acquire_fence_completed"] ) {
            NSMutableDictionary *bad = clone(f); [bad[@"native"][@"reacquisitions"][20] removeObjectForKey:key];
            check(![validate(bad)[@"buffer_reuse_verified"] boolValue]);
        }
        for (NSString *key in @[@"serial", @"release", @"status", @"has_error", @"wire_sent", @"actual_gpu_terminal_callback", @"registry_id"] ) {
            NSMutableDictionary *bad = clone(f); [bad[@"native"][@"releases"][55] removeObjectForKey:key];
            check(![validate(bad)[@"buffer_reuse_verified"] boolValue]);
        }
        for (NSString *key in @[@"gpu_submitted", @"gpu_completed", @"consumer_status", @"consumer_error", @"generation", @"phase", @"resource_id", @"drawable_registry_id", @"drawable_presented", @"completion_join_retired"] ) {
            NSMutableDictionary *bad = clone(f); [bad[@"screen"][@"frames"][60] removeObjectForKey:key];
            check(![validate(bad)[@"buffer_reuse_verified"] boolValue]);
        }
        NSMutableDictionary *bad = clone(f); bad[@"screen"][@"frames"][0][@"presented_seconds"] = @0;
        check([validate(bad)[@"buffer_reuse_verified"] boolValue]); check(![validate(bad)[@"presentation_verified"] boolValue]);
        bad = clone(f); bad[@"native"][@"images"][119][@"mismatches"] = @1;
        check(![validate(bad)[@"buffer_reuse_verified"] boolValue]);
        bad = clone(f); bad[@"native"][@"images"][42][@"pixels_checked"] = @921600;
        check(![validate(bad)[@"buffer_reuse_verified"] boolValue]);
        bad = clone(f); bad[@"serial"] = [bad[@"serial"] stringByReplacingOccurrencesOfString:@"MPC_MOVE_GUEST_EXIT=0" withString:@"MPC_MOVE_GUEST_EXIT=99"];
        check(![validate(bad)[@"buffer_reuse_verified"] boolValue]);
        bad = clone(f);
        for (NSUInteger i = 0; i < 120; ++i) bad[@"screen"][@"frames"][i][@"drawable_id"] = @(i % 2);
        check([validate(bad)[@"buffer_reuse_verified"] boolValue]);
        printf("MOVING_RECEIPT_TESTS_PASSED checks=%u scope=synthetic-rejection-only gpu_verified=0\n",checks);
    }
}
