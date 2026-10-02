#import "ProbeBridge.h"
#import <Metal/Metal.h>
#import <UIKit/UIKit.h>
#include <dlfcn.h>
#include <mach/mach.h>
#include <sys/mman.h>
#include <sys/sysctl.h>
#include <sys/utsname.h>
#include <libkern/OSCacheControl.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <vector>
#include <time.h>

extern "C" kern_return_t mach_vm_remap(vm_map_t, mach_vm_address_t *, mach_vm_size_t,
    mach_vm_offset_t, int, vm_map_t, mach_vm_address_t, boolean_t, vm_prot_t *, vm_prot_t *, vm_inherit_t);

#if defined(__aarch64__)
// External debugger protocol ABI, not a CPU/Linux compatibility engine.
// Universal script command 1 prepares an RX alias; command 2 configures the
// upstream engine's legacy region callback; command 0 detaches after allocation.
__attribute__((naked, noinline)) static void *prepareDebuggerRX(void *, size_t) {
    __asm__("mov x16, #1\n brk #0xf00d\n ret");
}
__attribute__((naked, noinline)) static void configureDebuggerCallbacks(const char *, size_t) {
    __asm__("mov x16, #2\n brk #0xf00d\n ret");
}
__attribute__((naked, noinline)) static void detachDebugger(void) {
    __asm__("mov x16, #0\n brk #0xf00d\n ret");
}
#endif

static double threadCPUSeconds() {
    struct timespec value = {};
    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &value)) return -1;
    return value.tv_sec + value.tv_nsec / 1e9;
}
NSDictionary *MPCNativeCPUProbe(void) {
    NSMutableArray *trials = [NSMutableArray array];
    BOOL correct = YES;
    for (int trial = 0; trial < 5; ++trial) {
        uint64_t value = 1;
        double cpuStart = threadCPUSeconds();
        double wallStart = NSProcessInfo.processInfo.systemUptime;
        for (int i = 0; i < 1000000; ++i) {
            value ^= value >> 12; value ^= value << 25; value ^= value >> 27;
            value *= UINT64_C(2685821657736338717);
        }
        double wallMS = (NSProcessInfo.processInfo.systemUptime - wallStart) * 1000;
        double cpuEnd = threadCPUSeconds();
        correct = correct && value == UINT64_C(0x1d250c45a7bbc87e);
        [trials addObject:@{@"wall_ms": @(wallMS),
            @"thread_cpu_ms": cpuStart >= 0 && cpuEnd >= 0 ? @((cpuEnd - cpuStart) * 1000) : [NSNull null],
            @"checksum": [NSString stringWithFormat:@"%016llx", (unsigned long long)value]}];
    }
    return @{@"status": correct ? @"passed" : @"failed", @"execution": @"native-ios-arm64",
        @"algorithm": @"same-xorshift64star-as-linux-abi-gate", @"iterations_per_trial": @1000000,
        @"trials": trials, @"linux_execution": @NO, @"game_performance": @NO};
}

static double nowSeconds() { return NSProcessInfo.processInfo.systemUptime; }
static NSString *systemString(const char *name) {
    size_t size = 0;
    if (sysctlbyname(name, nullptr, &size, nullptr, 0) || !size || size > 4096) return @"unavailable";
    std::vector<char> bytes(size + 1, 0);
    if (sysctlbyname(name, bytes.data(), &size, nullptr, 0)) return @"unavailable";
    return [NSString stringWithUTF8String:bytes.data()] ?: @"unavailable";
}
static NSDictionary *codeSigning() {
    // Status query only. A debugger flag is not by itself a successful JIT test.
    using CSOps = int (*)(pid_t, unsigned int, void *, size_t);
    CSOps query = reinterpret_cast<CSOps>(dlsym(RTLD_DEFAULT, "csops"));
    uint32_t flags = 0;
    int result = query ? query(getpid(), 0, &flags, sizeof(flags)) : -1;
    int error = query && result ? errno : 0;
    int name[] = {CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()};
    struct kinfo_proc process = {};
    size_t processBytes = sizeof(process);
    int tracedResult = sysctl(name, 4, &process, &processBytes, nullptr, 0);
    return @{@"query_available": @(query != nullptr), @"query_result": @(result),
             @"errno": @(error), @"flags": @(flags),
             @"debugged": @(result == 0 && (flags & 0x10000000u) != 0),
             @"get_task_allow": @(result == 0 && (flags & 0x4u) != 0),
             @"traced_query_result": @(tracedResult),
             @"debugger_attached": @(tracedResult == 0 && (process.kp_proc.p_flag & P_TRACED) != 0)};
}

BOOL MPCDetachJITDebugger(void) {
#if defined(__aarch64__)
    if (![codeSigning()[@"debugger_attached"] boolValue]) return NO;
    if (!MPCDiagnosticStage(@"jit-before-debugger-detach", @{})) return NO;
    detachDebugger();
    MPCDiagnosticStage(@"jit-debugger-detach-returned", @{});
    return YES;
#else
    return NO;
#endif
}
NSDictionary *MPCPlatformFacts(void) {
    struct utsname info = {};
    uname(&info);
    task_vm_info_data_t vm = {};
    mach_msg_type_number_t count = TASK_VM_INFO_COUNT;
    kern_return_t memoryResult = task_info(mach_task_self(), TASK_VM_INFO,
                                         reinterpret_cast<task_info_t>(&vm), &count);
    id<MTLDevice> gpu = MTLCreateSystemDefaultDevice();
    return @{@"device_machine": [NSString stringWithUTF8String:info.machine] ?: @"unknown",
             @"ios_version": UIDevice.currentDevice.systemVersion,
             @"os_build": systemString("kern.osversion"),
             @"kernel": [NSString stringWithUTF8String:info.release] ?: @"unknown",
             @"host_page_bytes": @(getpagesize()),
             @"physical_memory_bytes": @(NSProcessInfo.processInfo.physicalMemory),
             @"physical_footprint_bytes": memoryResult == KERN_SUCCESS ? @(vm.phys_footprint) : [NSNull null],
             @"logical_processors": @(NSProcessInfo.processInfo.processorCount),
             @"thermal_state": @(NSProcessInfo.processInfo.thermalState),
             @"low_power_mode": @(NSProcessInfo.processInfo.lowPowerModeEnabled),
             @"metal_device": gpu.name ?: @"unavailable", @"code_signing": codeSigning(),
             @"public_ios_hypervisor_api": @NO};
}
NSDictionary *MPCExecuteJITProbe(void) {
    MPCDiagnosticStage(@"jit-signing-query", @{});
    NSDictionary *signing = codeSigning();
    MPCDiagnosticStage(@"jit-signing-result", signing);
    if (![signing[@"debugged"] boolValue] || ![signing[@"debugger_attached"] boolValue]) {
        return @{@"status": @"skipped", @"reason": @"Use Enable JIT in StikDebug for this running app with universal.js. An attached script debugger is required before preparing new executable regions.",
                 @"code_signing": signing, @"linux_execution": @NO};
    }
#if defined(__aarch64__)
    size_t size = static_cast<size_t>(getpagesize());
    if (!MPCDiagnosticStage(@"jit-before-mmap-rx", @{@"bytes": @(size)}))
        return @{@"status": @"failed", @"stage": @"diagnostic-write", @"linux_execution": @NO};
    void *mapping = mmap(nullptr, size, PROT_READ | PROT_EXEC, MAP_PRIVATE | MAP_ANON, -1, 0);
    if (mapping == MAP_FAILED) {
        int error = errno; MPCDiagnosticStage(@"jit-mmap-failed", @{@"errno": @(error)});
        return @{@"status": @"failed", @"stage": @"mmap-rx", @"errno": @(error), @"linux_execution": @NO};
    }
    mach_vm_address_t rx = 0;
    vm_prot_t current = 0, maximum = 0;
    MPCDiagnosticStage(@"jit-before-remap-rx-alias", @{});
    kern_return_t remap = mach_vm_remap(mach_task_self(), &rx, size, 0, VM_FLAGS_ANYWHERE,
        mach_task_self(), reinterpret_cast<mach_vm_address_t>(mapping), false, &current, &maximum, VM_INHERIT_NONE);
    if (remap != KERN_SUCCESS) {
        munmap(mapping, size);
        return @{@"status": @"failed", @"stage": @"remap-rx-alias", @"mach_error": @(remap), @"linux_execution": @NO};
    }
    if (!MPCDiagnosticStage(@"jit-before-universal-prepare-rx", @{})) {
        munmap(reinterpret_cast<void *>(rx), size);
        munmap(mapping, size);
        return @{@"status": @"failed", @"stage": @"diagnostic-write", @"linux_execution": @NO};
    }
    void *prepared = prepareDebuggerRX(reinterpret_cast<void *>(rx), size);
    if (prepared != reinterpret_cast<void *>(rx)) {
        munmap(reinterpret_cast<void *>(rx), size); munmap(mapping, size);
        return @{@"status": @"failed", @"stage": @"universal-prepare-return", @"linux_execution": @NO};
    }
    // The pinned QEMU allocator uses brk 0x69. Configure that one fixed region
    // callback through universal's command API; never execute user scripts.
    static const char callback[] = "legacyCommands[0x69] = JIT26PrepareRegion;";
    MPCDiagnosticStage(@"jit-before-configure-qemu-region-callback", @{});
    configureDebuggerCallbacks(callback, sizeof(callback) - 1);
    MPCDiagnosticStage(@"jit-before-mprotect-writable-alias", @{});
    if (mprotect(mapping, size, PROT_READ | PROT_WRITE)) {
        int error = errno;
        MPCDiagnosticStage(@"jit-mprotect-failed", @{@"errno": @(error)});
        munmap(reinterpret_cast<void *>(rx), size); munmap(mapping, size);
        return @{@"status": @"failed", @"stage": @"mprotect-writable-alias", @"errno": @(error), @"linux_execution": @NO};
    }
    const uint32_t code[] = {0x52800540, 0xd65f03c0}; // Our fixed mov w0,#42; ret.
    memcpy(mapping, code, sizeof(code));
    sys_dcache_flush(mapping, sizeof(code));
    sys_icache_invalidate(reinterpret_cast<void *>(rx), sizeof(code));
    if (!MPCDiagnosticStage(@"jit-before-execute", @{})) {
        munmap(reinterpret_cast<void *>(rx), size); munmap(mapping, size);
        return @{@"status": @"failed", @"stage": @"diagnostic-write", @"linux_execution": @NO};
    }
    int result = reinterpret_cast<int (*)(void)>(rx)();
    MPCDiagnosticStage(@"jit-returned", @{@"returned": @(result)});
    munmap(reinterpret_cast<void *>(rx), size); munmap(mapping, size);
    return @{@"status": result == 42 ? @"passed" : @"failed", @"returned": @(result),
             @"execution": @"native-arm64-local-jit-stub", @"protocol": @"stikdebug-universal-prepared-rx-writable-alias",
             @"qemu_region_callback": @"universal-configured-legacy-0x69", @"debugger_kept_for_engine_regions": @YES,
             @"linux_execution": @NO};
#else
    return @{@"status": @"skipped", @"reason": @"ARM64 device required", @"linux_execution": @NO};
#endif
}
NSDictionary *MPCMetalProbe(void) {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) return @{@"status": @"failed", @"stage": @"create-metal-device"};
        NSError *error = nil;
        NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
            "kernel void verify(device uint* output [[buffer(0)]], uint i [[thread_position_in_grid]]) {"
            " output[i] = (i * 1664525u + 1013904223u) ^ 0xa55aa55au; }";
        double begin = nowSeconds();
        id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
        id<MTLFunction> function = [library newFunctionWithName:@"verify"];
        id<MTLComputePipelineState> pipeline = function ? [device newComputePipelineStateWithFunction:function error:&error] : nil;
        if (!pipeline) return @{@"status": @"failed", @"stage": @"compile-compute", @"reason": error.localizedDescription ?: @"unknown"};
        double compileMS = (nowSeconds() - begin) * 1000;
        const size_t pixels = 1280 * 720;
        id<MTLBuffer> buffer = [device newBufferWithLength:pixels * sizeof(uint32_t) options:MTLResourceStorageModeShared];
        id<MTLCommandQueue> queue = [device newCommandQueue];
        id<MTLCommandBuffer> command = [queue commandBuffer];
        if (!buffer || !queue || !command) return @{@"status": @"failed", @"stage": @"allocate"};
        memset(buffer.contents, 0, pixels * sizeof(uint32_t));
        id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
        if (!encoder) return @{@"status": @"failed", @"stage": @"compute-encoder"};
        [encoder setComputePipelineState:pipeline];
        [encoder setBuffer:buffer offset:0 atIndex:0];
        NSUInteger threads = MIN(static_cast<NSUInteger>(256), pipeline.maxTotalThreadsPerThreadgroup);
        [encoder dispatchThreads:MTLSizeMake(pixels, 1, 1) threadsPerThreadgroup:MTLSizeMake(threads, 1, 1)];
        [encoder endEncoding];
        begin = nowSeconds();
        [command commit];
        [command waitUntilCompleted];
        double wallMS = (nowSeconds() - begin) * 1000;
        if (command.status != MTLCommandBufferStatusCompleted) return @{@"status": @"failed", @"stage": @"gpu-command", @"reason": command.error.localizedDescription ?: @"unknown"};
        const uint32_t *output = static_cast<const uint32_t *>(buffer.contents);
        size_t mismatches = 0;
        uint64_t checksum = 0;
        for (size_t i = 0; i < pixels; ++i) {
            uint32_t expected = (static_cast<uint32_t>(i) * 1664525u + 1013904223u) ^ 0xa55aa55au;
            mismatches += output[i] != expected;
            checksum += output[i];
        }
        return @{@"status": mismatches == 0 ? @"passed" : @"failed", @"device": device.name,
                 @"width": @1280, @"height": @720, @"values_verified": @(pixels), @"mismatches": @(mismatches),
                 @"checksum": @(checksum), @"compile_ms": @(compileMS), @"submit_to_completion_ms": @(wallMS),
                 @"gpu_ms": @((command.GPUEndTime - command.GPUStartTime) * 1000),
                 @"path": @"native-ios-metal-compute-shared-buffer-readback",
                 @"linux_graphics": @NO, @"game_fps": [NSNull null]};
    }
}
NSDictionary *MPCStorageProbe(void) {
    // New temporary file only, 32 MiB maximum. Never touches an existing disk.
    NSString *path = [NSTemporaryDirectory() stringByAppendingPathComponent:[NSString stringWithFormat:@"mypc-probe-%@", NSUUID.UUID.UUIDString]];
    int fd = open(path.fileSystemRepresentation, O_CREAT | O_EXCL | O_RDWR, 0600);
    if (fd < 0) return @{@"status": @"failed", @"stage": @"create", @"errno": @(errno)};
    constexpr size_t chunk = 1024 * 1024;
    constexpr size_t total = 32 * chunk;
    std::vector<uint8_t> data(chunk);
    for (size_t i = 0; i < chunk; ++i) data[i] = static_cast<uint8_t>((i * 17 + 31) % 251);
    double begin = nowSeconds();
    bool okay = true;
    int error = 0;
    for (size_t offset = 0; offset < total && okay; offset += chunk) {
        size_t done = 0;
        while (done < chunk) {
            ssize_t written = write(fd, data.data() + done, chunk - done);
            if (written < 0 && errno == EINTR) continue;
            if (written <= 0) { okay = false; error = errno; break; }
            done += static_cast<size_t>(written);
        }
    }
    if (okay && fsync(fd)) { okay = false; error = errno; }
    double writeMS = (nowSeconds() - begin) * 1000;
    if (okay && lseek(fd, 0, SEEK_SET) != 0) { okay = false; error = errno; }
    begin = nowSeconds();
    std::vector<uint8_t> readback(chunk);
    for (size_t offset = 0; offset < total && okay; offset += chunk) {
        size_t done = 0;
        while (done < chunk) {
            ssize_t got = read(fd, readback.data() + done, chunk - done);
            if (got < 0 && errno == EINTR) continue;
            if (got <= 0) { okay = false; error = errno; break; }
            done += static_cast<size_t>(got);
        }
        if (okay && memcmp(readback.data(), data.data(), chunk)) { okay = false; error = EIO; }
    }
    double readMS = (nowSeconds() - begin) * 1000;
    close(fd);
    int cleanup = unlink(path.fileSystemRepresentation);
    return @{@"status": okay && cleanup == 0 ? @"passed" : @"failed", @"bytes": @(total),
             @"write_and_fsync_ms": @(writeMS), @"cached_read_and_verify_ms": @(readMS),
             @"data_verified": @(okay), @"temporary_file_removed": @(cleanup == 0), @"errno": @(error),
             @"limitation": @"Small host sandbox file, cached reads; not guest disk or download throughput"};
}
