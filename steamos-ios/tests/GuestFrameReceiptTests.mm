#import "GuestFrameImport.h"
#include <cstdio>
static unsigned checks;
static NSMutableDictionary *fixture(void) {
    NSData *data=[NSData dataWithContentsOfFile:@"steamos-ios/tests/frame_sequence_fixture.json"];
    NSMutableDictionary *root=[NSJSONSerialization JSONObjectWithData:data options:NSJSONReadingMutableContainers error:nil];
    NSCAssert([root[@"phone_tested"] isEqual:@NO], @"Synthetic input only");
    return root[@"report"][@"tests"][@"linux_frames"];
}
static void expect(NSDictionary *g, BOOL importWanted, BOOL screenWanted, BOOL timingWanted) {
    NSString *nonce=g[@"run"];NSDictionary *imp=g[@"frame_import"];
    NSDictionary *r=MPCValidateGuestFrameImport(g[@"serial_tail"],nonce,imp[@"native"],YES,YES,YES);
    if ([r[@"host_memory_import_verified"] boolValue]!=importWanted) {
        fprintf(stderr,"Frame case %u import mismatch: got=%d wanted=%d pixels=%llu sum=%llu\n",checks,
            [r[@"host_memory_import_verified"] boolValue],importWanted,[r[@"pixels_checked"] unsignedLongLongValue],
            [r[@"channel_sum"] unsignedLongLongValue]); abort();
    }
    NSMutableDictionary *joined=[imp mutableCopy];joined[@"host_memory_import_verified"]=r[@"host_memory_import_verified"];
    NSDictionary *screen=MPCValidateGuestFrameScreen(nonce,joined,g[@"frame_screen"][@"native"],YES);
    if ([screen[@"gpu_sequence_verified"] boolValue]!=screenWanted || [screen[@"presentation_verified"] boolValue]!=timingWanted) {
        fprintf(stderr,"Frame case %u screen mismatch: gpu=%d wanted=%d timing=%d wanted=%d\n",checks,
            [screen[@"gpu_sequence_verified"] boolValue],screenWanted,[screen[@"presentation_verified"] boolValue],timingWanted); abort();
    }
    for(NSString *key in @[@"gameplay_verified",@"frame_pacing_verified",@"continuous_animation_verified",@"zero_copy_transport_verified"])
        if([screen[key] boolValue]) abort();
    checks++;
}
int main(void) { @autoreleasepool {
    expect(fixture(),YES,YES,NO);
    for(unsigned i=0;i<8;i++) {
        for(NSString *key in @[@"resource_id",@"phase",@"row_pitch",@"native_pixel_format",@"native_registry_id",@"backing_bytes",@"native_buffer_alias_verified",@"pixel_verification_performed"]) {
            NSMutableDictionary *g=fixture();g[@"frame_import"][@"native"][@"images"][i][key]=@99999;
            expect(g,NO,NO,NO);
        }
        for(NSString *key in @[@"resource_id",@"gpu_completed",@"consumer_status",@"consumer_error",@"completion_join_retired",@"presentation_on_main_thread",@"presentation_application_state",@"source_registry_id",@"geometry",@"gpu_end_seconds"]) {
            NSMutableDictionary *g=fixture();g[@"frame_screen"][@"native"][@"frames"][i][key]=@99999;
            expect(g,YES,NO,NO);
        }
    }
    NSMutableDictionary *g=fixture();
    for(NSMutableDictionary *f in g[@"frame_screen"][@"native"][@"frames"]) f[@"presented_seconds_later_query"]=@999;
    expect(g,YES,YES,NO);
    for(NSMutableDictionary *f in g[@"frame_screen"][@"native"][@"frames"]) f[@"presented_seconds"]=@([f[@"submit_seconds"] doubleValue]+.016);
    expect(g,YES,YES,YES);
    g=fixture();g[@"frame_screen"][@"native"][@"interrupted"]=@YES;expect(g,YES,NO,NO);
    g=fixture();g[@"serial_tail"]=[g[@"serial_tail"] stringByAppendingString:@"MPC_FRAME_GUEST_EXIT=0\n"];expect(g,NO,NO,NO);
    printf("FRAME_RECEIPT_CONTROLS_OK checks=%u synthetic-only; zero display timestamps never pass timing\n",checks);
} }
