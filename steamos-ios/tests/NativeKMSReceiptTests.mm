#import "../NativeKMS/Bridge.h"
#include <assert.h>
int main(int argc,const char **argv) {
    @autoreleasepool {
        assert(argc==2);
        NSData *data=[NSData dataWithContentsOfFile:[NSString stringWithUTF8String:argv[1]]];
        NSDictionary *all=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
        NSDictionary *f=all[@"valid"];
        NSDictionary *r=MPCNativeKMSReceipt(f[@"serial"],f[@"nonce"],f[@"native"],YES);
        assert([r[@"standard_kms_native_completion_verified"] isEqual:@YES]);
        NSMutableDictionary *reordered=[f[@"native"] mutableCopy];
        reordered[@"recent_terminals"]=[[f[@"native"][@"recent_terminals"] reverseObjectEnumerator] allObjects];
        assert([MPCNativeKMSReceipt(f[@"serial"],f[@"nonce"],reordered,YES)[@"standard_kms_native_completion_verified"] isEqual:@YES]);
        assert([MPCNativeKMSReceipt(f[@"serial"],f[@"nonce"],f[@"native"],NO)[@"standard_kms_native_completion_verified"] isEqual:@NO]);
        for(NSDictionary *bad in all[@"invalid"])
            assert([MPCNativeKMSReceipt(bad[@"serial"],bad[@"nonce"],bad[@"native"],YES)[@"standard_kms_native_completion_verified"] isEqual:@NO]);
        printf("Actual production KMS receipt accepted synthetic valid fixture and rejected %lu controls; no device evidence.\n",(unsigned long)[all[@"invalid"] count]+1);
    }
}
