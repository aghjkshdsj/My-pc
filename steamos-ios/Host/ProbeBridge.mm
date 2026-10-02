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
    return @{@"query_available": @(query != nullptr), @"query_result": @(result),
             @"errno": @(error), @"flags": @(flags),
             @"debugged": @(result == 0 && (flags & 0x10000000u) != 0)};
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
    NSDictionary *signing = codeSigning();
    if (![signing[@"debugged"] boolValue]) {
        return @{@"status": @"skipped", @"reason": @"Enable StikDebug for this app first. Debugged code-signing status was not observed.",
                 @"code_signing": signing, @"linux_execution": @NO};
    }
#if defined(__aarch64__)
    size_t size = static_cast<size_t>(getpagesize());
    void *mapping = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
    if (mapping == MAP_FAILED) return @{@"status": @"failed", @"stage": @"mmap-rw", @"errno": @(errno), @"linux_execution": @NO};
    // mov w0, #42; ret. Executes only our fixed, local diagnostic bytes.
    const uint32_t code[] = {0x52800540, 0xd65f03c0};
    memcpy(mapping, code, sizeof(code));
    sys_icache_invalidate(mapping, sizeof(code));
    if (mprotect(mapping, size, PROT_READ | PROT_EXEC)) {
        int error = errno;
        munmap(mapping, size);
        return @{@"status": @"failed", @"stage": @"mprotect-rx", @"errno": @(error), @"linux_execution": @NO};
    }
    int result = reinterpret_cast<int (*)(void)>(mapping)();
    munmap(mapping, size);
    return @{@"status": result == 42 ? @"passed" : @"failed", @"returned": @(result),
             @"execution": @"native-arm64-local-jit-stub", @"linux_execution": @NO};
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
