#import "ProbeBridge.h"
#include <CommonCrypto/CommonDigest.h>
#include <dlfcn.h>
#include <atomic>
#include <vector>
#include <string>
#include <thread>
#include <chrono>

// Fresh host adapter to the documented upstream QEMU library entry points.
// The CPU gate intentionally has no guest GPU, networking or persistent disk.
static std::atomic<bool> attempted(false), finished(false);
static std::atomic<int> engineStatus(-999);

static NSString *sha256(NSData *data) {
    CC_SHA256_CTX context;
    CC_SHA256_Init(&context);
    const auto *bytes = static_cast<const unsigned char *>(data.bytes);
    NSUInteger remaining = data.length;
    while (remaining) {
        CC_LONG count = static_cast<CC_LONG>(MIN(remaining, static_cast<NSUInteger>(1 << 20)));
        CC_SHA256_Update(&context, bytes, count);
        bytes += count;
        remaining -= count;
    }
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256_Final(digest, &context);
    NSMutableString *text = [NSMutableString string];
    for (unsigned char value : digest) [text appendFormat:@"%02x", value];
    return text;
}

static NSDictionary *failure(NSString *stage, NSString *reason) {
    return @{@"status": @"failed", @"stage": stage, @"reason": reason,
             @"linux_execution": @NO, @"steamos": @NO, @"graphics_tested": @NO};
}

NSDictionary *MPCLinuxKernelProbe(void) {
    @autoreleasepool {
        MPCDiagnosticStage(@"linux-gate-starting", @{});
        NSString *framework = [NSBundle.mainBundle.privateFrameworksPath
                              stringByAppendingPathComponent:@"qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu"];
        NSString *payload = [NSBundle.mainBundle.resourcePath stringByAppendingPathComponent:@"LinuxGate"];
        NSString *image = [payload stringByAppendingPathComponent:@"Image"];
        NSString *initramfs = [payload stringByAppendingPathComponent:@"initramfs.cpio.gz"];
        if (![NSFileManager.defaultManager fileExistsAtPath:framework] ||
            ![NSFileManager.defaultManager fileExistsAtPath:image] ||
            ![NSFileManager.defaultManager fileExistsAtPath:initramfs]) {
            return @{@"status": @"unavailable", @"reason": @"This build has no complete Linux engine/payload. Install an engine-bearing Linux gate prerelease.",
                     @"linux_execution": @NO, @"steamos": @NO, @"graphics_tested": @NO};
        }
        MPCDiagnosticStage(@"linux-jit-precondition", @{});
        NSDictionary *jit = MPCExecuteJITProbe();
        if (![jit[@"status"] isEqual:@"passed"]) return @{@"status": @"skipped", @"stage": @"jit-precondition", @"jit": jit, @"linux_execution": @NO};
        NSData *receiptData = [NSData dataWithContentsOfFile:[payload stringByAppendingPathComponent:@"payload-receipt.json"]];
        NSError *error = nil;
        NSDictionary *receipt = receiptData ? [NSJSONSerialization JSONObjectWithData:receiptData options:0 error:&error] : nil;
        if (![receipt isKindOfClass:NSDictionary.class] || ![receipt[@"kind"] isEqual:@"disposable-linux-abi-gate"])
            return failure(@"payload-receipt", error.localizedDescription ?: @"Missing payload provenance");
        for (NSString *name in @[@"Image", @"initramfs.cpio.gz"]) {
            NSDictionary *expected = receipt[@"files"][name];
            NSData *data = [NSData dataWithContentsOfFile:[payload stringByAppendingPathComponent:name] options:NSDataReadingMappedIfSafe error:&error];
            if (!data || data.length != [expected[@"bytes"] unsignedLongLongValue] || ![sha256(data) isEqual:expected[@"sha256"]])
                return failure(@"payload-sha256", [@"Input mismatch: " stringByAppendingString:name]);
        }
        // QEMU global state cannot be initialized twice safely in this process.
        if (attempted.exchange(true)) return failure(@"one-run-per-process", @"Close and relaunch the app before another Linux boot.");
        MPCDiagnosticStage(@"linux-before-dlopen-engine", @{});
        void *library = dlopen(framework.fileSystemRepresentation, RTLD_NOW | RTLD_LOCAL);
        if (!library) return failure(@"dlopen-engine", [NSString stringWithUTF8String:dlerror()] ?: @"Unknown loader error");
        using Init = void (*)(int, char **);
        using Loop = int (*)(void);
        using Cleanup = void (*)(int);
        using Unlock = void (*)(void);
        auto initialize = reinterpret_cast<Init>(dlsym(library, "qemu_init"));
        auto loop = reinterpret_cast<Loop>(dlsym(library, "qemu_main_loop"));
        auto cleanup = reinterpret_cast<Cleanup>(dlsym(library, "qemu_cleanup"));
        auto unlockBQL = reinterpret_cast<Unlock>(dlsym(library, "bql_unlock"));
        auto unlockReplay = reinterpret_cast<Unlock>(dlsym(library, "replay_mutex_unlock"));
        if (!initialize || !loop || !cleanup || !unlockBQL || !unlockReplay)
            return failure(@"engine-exports", @"Required pinned QEMU entry points unavailable");
        MPCDiagnosticStage(@"linux-engine-loaded", @{});
        NSString *nonce = [NSUUID.UUID.UUIDString.lowercaseString stringByReplacingOccurrencesOfString:@"-" withString:@""];
        NSURL *documents = [NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask][0];
        NSURL *directory = [documents URLByAppendingPathComponent:[@"LinuxGate-" stringByAppendingString:nonce] isDirectory:YES];
        if (![NSFileManager.defaultManager createDirectoryAtURL:directory withIntermediateDirectories:NO attributes:nil error:&error])
            return failure(@"create-run-directory", error.localizedDescription);
        NSString *serial = [[directory URLByAppendingPathComponent:@"serial.log"] path];
        NSArray<NSString *> *arguments = @[@"qemu-system-aarch64", @"-machine", @"virt", @"-cpu", @"max",
            @"-accel", @"tcg,thread=multi", @"-smp", @"2", @"-m", @"512", @"-nodefaults", @"-display", @"none",
            @"-chardev", [NSString stringWithFormat:@"file,id=serial0,path=%@", serial], @"-serial", @"chardev:serial0",
            @"-monitor", @"none", @"-kernel", image, @"-initrd", initramfs, @"-append",
            [@"console=ttyAMA0 rdinit=/init panic=1 mpc_run=" stringByAppendingString:nonce], @"-no-reboot"];
        NSMutableDictionary *run = [@{@"schema": @1, @"scope": @"physical-ios-linux-tcg-gate",
            @"status": @"running", @"run": nonce, @"device": MPCPlatformFacts(),
            @"source_commit": [NSBundle.mainBundle objectForInfoDictionaryKey:@"MPCSourceCommit"] ?: @"unknown",
            @"engine": @"qemu-10.0.12-utm-aarch64-tcg", @"hardware_virtualization": @NO,
            @"payload": receipt, @"linux_execution": @NO, @"steamos": @NO, @"graphics_tested": @NO,
            @"serial_file": @"serial.log"} mutableCopy];
        NSURL *reportURL = [directory URLByAppendingPathComponent:@"linux-test.json"];
        [[NSJSONSerialization dataWithJSONObject:run options:NSJSONWritingPrettyPrinted error:nil] writeToURL:reportURL atomically:YES];
        MPCDiagnosticStage(@"linux-pending-receipt-saved", @{@"run": nonce, @"relative_directory": directory.lastPathComponent});
        std::vector<std::string> values;
        for (NSString *arg in arguments) values.emplace_back(arg.UTF8String);
        double start = NSProcessInfo.processInfo.systemUptime;
        // The pinned qemu_init acquires BQL/replay locks. Keep them held for the
        // main loop/cleanup, matching upstream system/main.c, without its exit().
        std::thread([values = std::move(values), initialize, loop, cleanup, unlockBQL, unlockReplay]() mutable {
            @autoreleasepool {
                std::vector<char *> argv;
                for (auto &value : values) argv.push_back(value.data());
                argv.push_back(nullptr);
                MPCDiagnosticStage(@"linux-before-qemu-init", @{});
                initialize(static_cast<int>(argv.size() - 1), argv.data());
                MPCDiagnosticStage(@"linux-before-qemu-main-loop", @{});
                int status = loop();
                MPCDiagnosticStage(@"linux-before-qemu-cleanup", @{@"engine_status": @(status)});
                cleanup(status);
                unlockBQL();
                unlockReplay();
                engineStatus.store(status);
                finished.store(true);
                MPCDiagnosticStage(@"linux-engine-finished", @{@"engine_status": @(status)});
            }
        }).detach();
        while (!finished.load() && NSProcessInfo.processInfo.systemUptime - start < 180)
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        run[@"elapsed_ms"] = @((NSProcessInfo.processInfo.systemUptime - start) * 1000);
        run[@"engine_finished"] = @(finished.load());
        run[@"engine_status"] = @(engineStatus.load());
        NSString *text = [NSString stringWithContentsOfFile:serial encoding:NSUTF8StringEncoding error:&error] ?: @"";
        run[@"serial_tail"] = text.length > 16000 ? [text substringFromIndex:text.length - 16000] : text;
        NSMutableArray<NSDictionary *> *guestRows = [NSMutableArray array];
        for (NSString *line in [text componentsSeparatedByCharactersInSet:NSCharacterSet.newlineCharacterSet]) {
            NSRange marker = [line rangeOfString:@"MPC_LINUX_ABI "];
            if (marker.location == NSNotFound) continue;
            NSData *json = [[line substringFromIndex:NSMaxRange(marker)] dataUsingEncoding:NSUTF8StringEncoding];
            id guest = [NSJSONSerialization JSONObjectWithData:json options:0 error:nil];
            if ([guest isKindOfClass:NSDictionary.class]) [guestRows addObject:guest];
        }
        BOOL passed = finished.load() && engineStatus.load() == 0 && guestRows.count == 1;
        NSDictionary *guest = guestRows.firstObject ?: @{};
        passed = passed && [guest[@"schema"] isEqual:@1] && [guest[@"run"] isEqual:nonce] &&
            [guest[@"machine"] isEqual:@"aarch64"] && [guest[@"elf_arch"] isEqual:@"aarch64"] &&
            [guest[@"page_bytes"] isEqual:@4096] && [guest[@"failures"] isEqual:@0] &&
            [guest[@"checksum"] isEqual:@"1d250c45a7bbc87e"] && [text containsString:@"MPC_LINUX_EXIT=0"];
        for (NSString *key in @[@"signals", @"mmap_protection", @"pthread_tls_futex", @"fork_exec"])
            passed = passed && [guest[key] isEqual:@YES];
        run[@"guest"] = guest;
        run[@"status"] = passed ? @"passed" : (finished.load() ? @"failed" : @"timed-out-engine-still-running");
        run[@"linux_execution"] = @(passed);
        run[@"after"] = MPCPlatformFacts();
        run[@"limitations"] = @"This disposable Linux kernel/ABI gate is not SteamOS, Steam, FEX or a game graphics/performance test. If timed out, close and relaunch the app. Serial and pending receipts survive an engine failure.";
        [[NSJSONSerialization dataWithJSONObject:run options:NSJSONWritingPrettyPrinted error:nil] writeToURL:reportURL atomically:YES];
        return run;
    }
}
