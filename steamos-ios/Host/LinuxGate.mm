#import "ProbeBridge.h"
#import "GuestMetalTrace.h"
#import "GuestImageImport.h"
#include <CommonCrypto/CommonDigest.h>
#include <dlfcn.h>
#include <atomic>
#include <vector>
#include <string>
#include <thread>
#include <chrono>
#include <sys/stat.h>
#include <unistd.h>

// Fresh host adapter to the documented upstream QEMU library entry points.
// CPU and guest-GPU gates share one QEMU initialization allowance. Neither uses
// a persistent disk or network, and neither is a complete SteamOS environment.
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
             @"requires_relaunch": @(attempted.load()),
             @"linux_execution": @NO, @"steamos": @NO, @"graphics_tested": @NO};
}

static NSDictionary *runKernel(BOOL graphics, BOOL images) {
    @autoreleasepool {
        MPCDiagnosticStage(@"linux-gate-starting", @{});
        if (attempted.load()) return failure(@"one-run-per-process", @"Close and relaunch, then request StikDebug for the new process before another Linux boot.");
        NSString *framework = [NSBundle.mainBundle.privateFrameworksPath
                              stringByAppendingPathComponent:@"qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu"];
        NSString *payload = [NSBundle.mainBundle.resourcePath stringByAppendingPathComponent:graphics ? @"LinuxGuestGPU" : @"LinuxGate"];
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
        if (!MPCConfigureQEMUJIT()) return failure(@"qemu-jit-callback", @"Enable StikDebug universal.js for this current process before the engine allocates executable regions.");
        NSData *receiptData = [NSData dataWithContentsOfFile:[payload stringByAppendingPathComponent:@"payload-receipt.json"]];
        NSError *error = nil;
        NSDictionary *receipt = receiptData ? [NSJSONSerialization JSONObjectWithData:receiptData options:0 error:&error] : nil;
        if (![receipt isKindOfClass:NSDictionary.class])
            return failure(@"payload-receipt", error.localizedDescription ?: @"Missing payload provenance");
        BOOL imagePayload = [receipt[@"scope"] isEqual:@"linux-arm64-graphics-payload-image-export-boot-controls"] &&
                            [receipt[@"image_gate_compiled"] isEqual:@YES];
        BOOL correctScope = graphics
            ? (imagePayload || (!images && [receipt[@"scope"] isEqual:@"linux-arm64-graphics-payload-missing-3d-boot-controls"]))
            : [receipt[@"kind"] isEqual:@"disposable-linux-abi-gate"];
        if (!correctScope)
            return failure(@"payload-receipt", error.localizedDescription ?: @"Missing payload provenance");
        for (NSString *name in @[@"Image", @"initramfs.cpio.gz"]) {
            NSDictionary *expected = receipt[@"files"][name];
            NSData *data = [NSData dataWithContentsOfFile:[payload stringByAppendingPathComponent:name] options:NSDataReadingMappedIfSafe error:&error];
            if (!data || data.length != [expected[@"bytes"] unsignedLongLongValue] || ![sha256(data) isEqual:expected[@"sha256"]])
                return failure(@"payload-sha256", [@"Input mismatch: " stringByAppendingString:name]);
        }
        NSDictionary *engineBundle = @{};
        NSMutableDictionary *observedGPUCodes = [NSMutableDictionary dictionary];
        if (graphics) {
            NSData *bundleData = [NSData dataWithContentsOfFile:[payload stringByAppendingPathComponent:@"engine-bundle.json"]];
            id parsed = bundleData ? [NSJSONSerialization JSONObjectWithData:bundleData options:0 error:nil] : nil;
            if (![parsed isKindOfClass:NSDictionary.class] ||
                ![parsed[@"scope"] isEqual:@"bundled-physical-ios-linux-guest-gpu-gate"])
                return failure(@"gpu-engine-receipt", @"Missing exact guest-GPU engine bundle provenance.");
            engineBundle = parsed;
            NSDictionary *identities = engineBundle[@"engine_text_sections"];
            if (![identities isKindOfClass:NSDictionary.class] || identities.count < 8 || identities.count > 32)
                return failure(@"gpu-engine-identities", @"Incomplete executable identities.");
            for (id relative in identities) {
                if (![relative isKindOfClass:NSString.class]) return failure(@"gpu-engine-path", @"Invalid engine path.");
                NSArray *parts = [relative componentsSeparatedByString:@"/"];
                if (parts.count != 2 || ![parts[0] hasSuffix:@".framework"] ||
                    ![[parts[0] stringByDeletingPathExtension] isEqual:parts[1]])
                    return failure(@"gpu-engine-path", @"Unexpected framework layout.");
                NSString *path = [NSBundle.mainBundle.privateFrameworksPath stringByAppendingPathComponent:relative];
                NSDictionary *actual = MPCFrameworkTextIdentity(path);
                if (!actual || ![actual isEqual:identities[relative]])
                    return failure(@"gpu-engine-text-sha256", [@"Engine code mismatch: " stringByAppendingString:relative]);
                observedGPUCodes[relative] = actual;
            }
            MPCDiagnosticStage(@"linux-guest-gpu-engine-identities-verified", @{@"framework_count": @(identities.count)});
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
        if (graphics) {
            using RegisterBackend = int (*)(void);
            auto registerBackend = reinterpret_cast<RegisterBackend>(dlsym(library, "mpc_qemu_register_egl_headless"));
            if (!registerBackend)
                return failure(@"gpu-display-backend-unavailable", @"This engine has no compiled EGL-headless backend. Install the corrected GPU prerelease; close and relaunch before retrying.");
            MPCDiagnosticStage(@"linux-before-headless-backend-registration", @{});
            if (registerBackend() != 1)
                return failure(@"gpu-display-backend-registration", @"The built-in EGL-headless backend could not be registered.");
            MPCDiagnosticStage(@"linux-headless-backend-registered", @{@"egl_metal_context_verified": @NO});
        }
        NSString *nonce = [NSUUID.UUID.UUIDString.lowercaseString stringByReplacingOccurrencesOfString:@"-" withString:@""];
        NSURL *documents = [NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask][0];
        NSURL *directory = [documents URLByAppendingPathComponent:[@"LinuxGate-" stringByAppendingString:nonce] isDirectory:YES];
        if (![NSFileManager.defaultManager createDirectoryAtURL:directory withIntermediateDirectories:NO attributes:nil error:&error])
            return failure(@"create-run-directory", error.localizedDescription);
        if (graphics) {
            // Explicit app-owned namespace for the renderer's immediately
            // unlinked communication files; never use a global shm namespace.
            NSURL *privateFiles = [directory URLByAppendingPathComponent:@"renderer-private" isDirectory:YES];
            if (![NSFileManager.defaultManager createDirectoryAtURL:privateFiles withIntermediateDirectories:NO
                    attributes:@{NSFilePosixPermissions: @0700} error:&error])
                return failure(@"renderer-private-directory", error.localizedDescription);
            struct stat info = {};
            if (lstat(privateFiles.path.fileSystemRepresentation, &info) != 0 || !S_ISDIR(info.st_mode) ||
                info.st_uid != geteuid() || (info.st_mode & 0777) != 0700 ||
                setenv("MPC_GPU_SHM_DIR", privateFiles.path.fileSystemRepresentation, 1) != 0)
                return failure(@"renderer-private-directory", @"Cannot prepare the app-owned renderer file namespace.");
            MPCDiagnosticStage(@"linux-private-file-directory-prepared", @{@"mode_0700": @YES,
                @"host_memory_import_verified": @NO});
            NSString *molten = [[NSBundle.mainBundle privateFrameworksPath]
                stringByAppendingPathComponent:@"MoltenVK.framework/MoltenVK"];
            if (!MPCGuestMetalTraceBegin(nonce, molten, &error))
                return failure(@"guest-metal-observer-unavailable", error.localizedDescription);
            MPCDiagnosticStage(@"linux-guest-metal-observer-configured", @{@"abi": @1,
                @"adds_gpu_work": @NO, @"metal_host_verified": @NO});
            if (images) {
                if (!MPCGuestImageImportBegin(nonce, library, &error))
                    return failure(@"native-image-adapter-unavailable", error.localizedDescription);
                MPCDiagnosticStage(@"linux-native-image-adapter-configured", @{@"abi": @1,
                    @"host_memory_import_verified": @NO, @"presentation_verified": @NO});
            }
        }
        NSString *serial = [[directory URLByAppendingPathComponent:@"serial.log"] path];
        NSString *kernelOptions = images ? @"console=ttyAMA0 rdinit=/init panic=1 mpc_image=1 mpc_run=" : @"console=ttyAMA0 rdinit=/init panic=1 mpc_run=";
        NSMutableArray<NSString *> *arguments = [@[@"qemu-system-aarch64", @"-machine", @"virt", @"-cpu", @"max",
            @"-accel", @"tcg,thread=multi,split-wx=on,tb-size=32", @"-smp", @"2", @"-m", @"512", @"-nodefaults", @"-display", graphics ? @"egl-headless,gl=es" : @"none",
            @"-chardev", [NSString stringWithFormat:@"file,id=serial0,path=%@", serial], @"-serial", @"chardev:serial0",
            @"-monitor", @"none", @"-kernel", image, @"-initrd", initramfs, @"-append",
            [kernelOptions stringByAppendingString:nonce], @"-no-reboot"] mutableCopy];
        if (graphics) [arguments addObjectsFromArray:@[@"-device", @"virtio-gpu-gl-pci,blob=on,venus=on,hostmem=128M,xres=1280,yres=720", @"-d", @"guest_errors"]];
        NSMutableDictionary *run = [@{@"schema": @1, @"scope": images ? @"physical-ios-linux-guest-image-gate" : graphics ? @"physical-ios-linux-guest-vulkan-gate" : @"physical-ios-linux-tcg-gate",
            @"status": @"running", @"run": nonce, @"device": MPCPlatformFacts(),
            @"source_commit": [NSBundle.mainBundle objectForInfoDictionaryKey:@"MPCSourceCommit"] ?: @"unknown",
            @"engine": @"qemu-10.0.12-utm-aarch64-tcg", @"hardware_virtualization": @NO,
            @"requested_jit_cache_mib": @32, @"split_wx_requested": @YES,
            @"payload": receipt, @"linux_execution": @NO, @"steamos": @NO, @"graphics_tested": @NO,
            @"serial_file": @"serial.log"} mutableCopy];
        run[@"requires_relaunch"] = @YES;
        if (graphics) {
            run[@"engine_bundle"] = engineBundle;
            run[@"host_private_file_directory_prepared"] = @YES;
            run[@"host_metal_completion_observer_requested"] = @YES;
            run[@"display_backend_registered"] = @YES;
            run[@"engine_text_sections_observed"] = observedGPUCodes;
            run[@"engine_text_sections_verified"] = @YES;
            run[@"guest_gpu_device_requested"] = @YES;
            run[@"guest_gpu_host_visible_mib"] = @128;
            run[@"guest_vulkan_pixels_verified"] = @NO;
            run[@"metal_host_verified"] = @NO;
            run[@"presentation_verified"] = @NO;
            run[@"host_memory_import_verified"] = @NO;
            run[@"image_import_requested"] = @(images);
            run[@"gameplay_verified"] = @NO;
            run[@"route_requested"] = @"Linux ARM64 Mesa Venus â†’ virtio-GPU â†’ native iOS virgl/Venus â†’ MoltenVK â†’ Metal";
        }
        NSURL *reportURL = [directory URLByAppendingPathComponent:@"linux-test.json"];
        [[NSJSONSerialization dataWithJSONObject:run options:NSJSONWritingPrettyPrinted error:nil] writeToURL:reportURL atomically:YES];
        MPCDiagnosticStage(@"linux-pending-receipt-saved", @{@"run": nonce, @"relative_directory": directory.lastPathComponent});
        MPCDiagnosticStage(@"linux-engine-configuration", @{@"jit_cache_mib": @32, @"split_wx": @YES, @"vcpus": @2, @"guest_ram_mib": @512});
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
                MPCDiagnosticStage(@"linux-qemu-init-returned", @{});
                // QEMU's initial TCG regions have been prepared. Release the
                // debugger before the workload; new regions would need reattach.
                MPCDetachJITDebugger();
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
        BOOL linuxPassed = passed;
        if (graphics) {
            NSDictionary *gpu = MPCParseGuestGPUReceipt(text, nonce, linuxPassed);
            [run addEntriesFromDictionary:gpu];
            passed = [gpu[@"guest_vulkan_pixels_verified"] isEqual:@YES];
            MPCDiagnosticStage(@"linux-guest-vulkan-receipt-checked", @{
                @"guest_pixels_verified": gpu[@"guest_vulkan_pixels_verified"],
                @"driver_detected": gpu[@"graphics_kernel_device_detected"],
                @"nonce_bound": gpu[@"fresh_guest_vulkan_nonce_bound"]});
            NSDictionary *metal = MPCGuestMetalTraceFinish(passed);
            run[@"native_metal_trace"] = metal;
            run[@"metal_host_verified"] = metal[@"metal_host_verified"];
            MPCDiagnosticStage(@"linux-guest-metal-completion-checked", @{
                @"metal_host_verified": metal[@"metal_host_verified"],
                @"observed_commit_points": metal[@"observed_commit_points"],
                @"pending": metal[@"pending"], @"failed": metal[@"failed"]});
            if (images) {
                NSDictionary *import = MPCGuestImageImportFinish(text, finished.load() && engineStatus.load() == 0,
                    linuxPassed, [metal[@"metal_host_verified"] isEqual:@YES]);
                run[@"image_import"] = import;
                run[@"host_memory_import_verified"] = import[@"host_memory_import_verified"];
                passed = passed && [import[@"host_memory_import_verified"] isEqual:@YES];
                MPCDiagnosticStage(@"linux-native-image-import-checked", @{
                    @"host_memory_import_verified": import[@"host_memory_import_verified"], @"presentation_verified": @NO});
            }
        }
        run[@"guest"] = guest;
        run[@"status"] = passed ? @"passed" : (finished.load() ? @"failed" : @"timed-out-engine-still-running");
        run[@"linux_execution"] = @(linuxPassed);
        run[@"after"] = MPCPlatformFacts();
        run[@"limitations"] = @"This disposable Linux kernel/ABI gate is not SteamOS, Steam, FEX or a game graphics/performance test. If timed out, close and relaunch the app. Serial and pending receipts survive an engine failure.";
        if (graphics) run[@"limitations"] = @"Guest Vulkan pixels and the native MoltenVK command-completion observer have separate receipts. Completed native command buffers do not prove host-memory import, zero-copy, moving presentation or game FPS. This is a disposable Linux graphics test, not SteamOS/Steam/FEX. Share logs after failure; relaunch before another Linux boot.";
        if (images) run[@"limitations"] = @"The image gate correlates two immutable Linux-rendered images with their native Metal buffer layouts, GPU consumers and cleanup. Its bounded diagnostic readbacks are correctness checks. Visible presentation, production zero-copy transport, SteamOS/Steam/FEX and game performance remain unfinished.";
        [[NSJSONSerialization dataWithJSONObject:run options:NSJSONWritingPrettyPrinted error:nil] writeToURL:reportURL atomically:YES];
        return run;
    }
}

NSDictionary *MPCLinuxKernelProbe(void) { return runKernel(NO, NO); }
NSDictionary *MPCLinuxGuestGPUProbe(void) { return runKernel(YES, NO); }
NSDictionary *MPCLinuxGuestImageProbe(void) { return runKernel(YES, YES); }
