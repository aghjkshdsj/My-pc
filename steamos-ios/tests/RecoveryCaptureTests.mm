#import "ProbeBridge.h"
#include <stdio.h>
#include <unistd.h>
#include <string.h>

// Hosted synthetic fixture, not JIT, Linux boot or physical iPhone evidence.
int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc != 3 || !MPCStartDiagnosticCapture([NSString stringWithUTF8String:argv[1]])) return 2;
        fprintf(stdout, "synthetic-engine-stdout\n");
        fprintf(stderr, "synthetic-engine-stderr\n");
        if (!MPCDiagnosticStage(@"before-abrupt-exit", @{@"fixture": @YES})) return 3;
        NSDictionary *snapshot = MPCDiagnosticOutputSnapshot([NSString stringWithUTF8String:argv[1]]);
        if (![snapshot[@"status"] isEqual:@"captured"] || [snapshot[@"tail_truncated"] boolValue] ||
            ![snapshot[@"tail"] containsString:@"synthetic-engine-stdout"] ||
            ![snapshot[@"tail"] containsString:@"synthetic-engine-stderr"]) return 4;
        // The normal device report must retain the latest failure even when
        // verbose engine output grows beyond the bounded sharing tail.
        for (unsigned int i = 0; i < 70000; ++i) fputc('x', stdout);
        fprintf(stdout, "\nsynthetic-latest-failure\n");
        snapshot = MPCDiagnosticOutputSnapshot([NSString stringWithUTF8String:argv[1]]);
        if (![snapshot[@"tail_truncated"] boolValue] || [snapshot[@"captured_bytes"] unsignedIntegerValue] != 65536 ||
            ![snapshot[@"tail"] hasSuffix:@"synthetic-latest-failure\n"]) return 5;
        if (!strcmp(argv[2], "abrupt")) _exit(77);
        MPCStopDiagnosticCapture();
        snapshot = MPCDiagnosticOutputSnapshot([NSString stringWithUTF8String:argv[1]]);
        if (![snapshot[@"status"] isEqual:@"captured"] || ![snapshot[@"tail_truncated"] boolValue] ||
            ![snapshot[@"tail"] hasSuffix:@"synthetic-latest-failure\n"]) return 6;
        fprintf(stdout, "stdout-restored\n");
        return 0;
    }
}
