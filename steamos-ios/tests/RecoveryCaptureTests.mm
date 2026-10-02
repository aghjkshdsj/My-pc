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
        if (!strcmp(argv[2], "abrupt")) _exit(77);
        MPCStopDiagnosticCapture();
        fprintf(stdout, "stdout-restored\n");
        return 0;
    }
}
