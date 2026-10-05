/* SPDX-License-Identifier: MIT */
#import "Bridge.h"
#import "../Host/NativeDisplayCompletion.h"
#import "../Host/GuestMetalTrace.h"
#import <QuartzCore/CAMetalLayer.h>
#include "../Host/QEMUInitThreadLease.h"
#include <CommonCrypto/CommonDigest.h>
#include <atomic>
#include <thread>
#include <chrono>
#include <vector>
#include <string>
#include <dlfcn.h>
#include <sys/stat.h>
#include <unistd.h>
extern CAMetalLayer *MPCNativeKMSVisibleLayer(void);
static std::atomic<bool> attempted(false),finished(false),rcuRetired(false);
static std::atomic<int> status(-999);
static NSString *sha(NSData *data) {
    CC_SHA256_CTX c;CC_SHA256_Init(&c);
    const auto *p=(const uint8_t *)data.bytes;NSUInteger remaining=data.length;
    while(remaining){CC_LONG n=(CC_LONG)MIN(remaining,(NSUInteger)(1<<20));CC_SHA256_Update(&c,p,n);p+=n;remaining-=n;}
    unsigned char bytes[CC_SHA256_DIGEST_LENGTH];CC_SHA256_Final(bytes,&c);
    NSMutableString *s=[NSMutableString string];for(unsigned char b:bytes)[s appendFormat:@"%02x",b];return s;
}
static NSDictionary *load(NSString *path) {
    NSData *data=[NSData dataWithContentsOfFile:path];
    id value=data?[NSJSONSerialization JSONObjectWithData:data options:0 error:nil]:nil;
    return [value isKindOfClass:NSDictionary.class]?value:nil;
}
static NSDictionary *fail(NSString *stage,NSString *reason) {
    MPCDiagnosticStage(stage,@{@"reason":reason?:@"unknown"});
    return @{@"status":@"failed",@"stage":stage,@"reason":reason?:@"unknown",@"requires_relaunch":@(attempted.load()),
        @"standard_kms_native_completion_verified":@NO,@"linux_execution":@NO,@"steamos":@NO};
}
NSDictionary *MPCNativeKMSRun(void) {
    @autoreleasepool {
        if(attempted.load())return fail(@"one-run-per-process",@"Relaunch and enable JIT for a new process.");
        NSString *root=[NSBundle.mainBundle.resourcePath stringByAppendingPathComponent:@"LinuxNativeKMS"];
        NSDictionary *payload=load([root stringByAppendingPathComponent:@"payload-receipt.json"]);
        NSDictionary *bundle=load([root stringByAppendingPathComponent:@"engine-bundle.json"]);
        if(![payload[@"scope"] isEqual:@"linux-standard-kms-native-completion-payload-rejection-controls"] ||
            ![bundle[@"scope"] isEqual:@"bundled-ios-standard-kms-native-completion"] ||
            ![payload[@"kernel_sha256"] isEqual:@"f5b28031447603bf2c66846cbdb503ccd35fa86106969af628752c733e188ee7"] ||
            ![bundle[@"completion_abi"] isEqual:@2])return fail(@"native-kms-provenance",@"Exact new engine and Linux payload are required.");
        for(NSString *name in @[@"Image",@"initramfs.cpio.gz"]) {
            NSData *data=[NSData dataWithContentsOfFile:[root stringByAppendingPathComponent:name] options:NSDataReadingMappedIfSafe error:nil];
            NSDictionary *expected=payload[@"files"][name];
            if(!data || data.length!=[expected[@"bytes"] unsignedLongLongValue] || ![sha(data) isEqual:expected[@"sha256"]])
                return fail(@"native-kms-payload-hash",name);
        }
        NSDictionary *identities=bundle[@"engine_text_sections"];
        if(![identities isKindOfClass:NSDictionary.class] || identities.count<8 || identities.count>32)
            return fail(@"native-kms-engine-identities",@"Incomplete code identities.");
        for(NSString *relative in identities) {
            NSArray *parts=[relative componentsSeparatedByString:@"/"];
            if(parts.count!=2 || ![parts[0] hasSuffix:@".framework"] ||
                ![[parts[0] stringByDeletingPathExtension] isEqual:parts[1]])return fail(@"native-kms-engine-path",relative);
            NSDictionary *actual=MPCFrameworkTextIdentity([NSBundle.mainBundle.privateFrameworksPath stringByAppendingPathComponent:relative]);
            if(![actual isEqual:identities[relative]])return fail(@"native-kms-engine-code",relative);
        }
        NSDictionary *jit=MPCExecuteJITProbe();
        if(![jit[@"status"] isEqual:@"passed"] || !MPCConfigureQEMUJIT())return fail(@"native-kms-jit",@"Enable StikDebug universal.js for this process first.");
        if(attempted.exchange(true))return fail(@"one-run-per-process",@"Relaunch before another Linux boot.");
        NSString *framework=[NSBundle.mainBundle.privateFrameworksPath stringByAppendingPathComponent:@"qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu"];
        void *engine=dlopen(framework.fileSystemRepresentation,RTLD_NOW|RTLD_LOCAL);
        if(!engine)return fail(@"native-kms-engine-load",[NSString stringWithUTF8String:dlerror()]);
        using Init=void(*)(int,char **);using Loop=int(*)(void);using Cleanup=void(*)(int);using Void=void(*)(void);
        auto init=(Init)dlsym(engine,"qemu_init");auto loop=(Loop)dlsym(engine,"qemu_main_loop");auto cleanup=(Cleanup)dlsym(engine,"qemu_cleanup");
        auto bql=(Void)dlsym(engine,"bql_unlock");auto replay=(Void)dlsym(engine,"replay_mutex_unlock");auto retire=(Void)dlsym(engine,"rcu_unregister_thread");
        auto registerBackend=(int(*)(void))dlsym(engine,"mpc_qemu_register_egl_headless");
        if(!init || !loop || !cleanup || !bql || !replay || !retire || !registerBackend || registerBackend()!=1)
            return fail(@"native-kms-engine-exports",@"Missing compiled engine entry points.");
        __block BOOL configured=NO;__block NSError *error=nil;
        dispatch_sync(dispatch_get_main_queue(),^{
            CAMetalLayer *layer=MPCNativeKMSVisibleLayer();
            if(layer)configured=MPCNativeDisplayCompletionBegin(engine,layer,&error);
        });
        if(!configured)return fail(@"native-kms-visible-surface",error.localizedDescription?:@"Keep the native screen visible in the foreground.");
        NSString *nonce=[NSUUID.UUID.UUIDString.lowercaseString stringByReplacingOccurrencesOfString:@"-" withString:@""];
        NSURL *documents=[NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask][0];
        NSURL *directory=[documents URLByAppendingPathComponent:[@"LinuxGate-" stringByAppendingString:nonce] isDirectory:YES];
        NSURL *files=[directory URLByAppendingPathComponent:@"renderer-private" isDirectory:YES];
        if(![NSFileManager.defaultManager createDirectoryAtURL:files withIntermediateDirectories:YES attributes:@{NSFilePosixPermissions:@0700} error:&error])
            return fail(@"native-kms-private-files",error.localizedDescription);
        struct stat info={};
        if(lstat(files.path.fileSystemRepresentation,&info) || !S_ISDIR(info.st_mode) || info.st_uid!=geteuid() ||
           (info.st_mode&0777)!=0700 || setenv("MPC_GPU_SHM_DIR",files.path.fileSystemRepresentation,1))
            return fail(@"native-kms-private-files",@"App-owned private renderer directory failed verification.");
        NSString *molten=[NSBundle.mainBundle.privateFrameworksPath stringByAppendingPathComponent:@"MoltenVK.framework/MoltenVK"];
        if(!MPCGuestMetalTraceBegin(nonce,molten,&error))return fail(@"native-kms-metal-observer",error.localizedDescription);
        NSString *serial=[directory.path stringByAppendingPathComponent:@"serial.log"];
        NSArray *arguments=@[@"qemu-system-aarch64",@"-machine",@"virt",@"-cpu",@"max",@"-accel",@"tcg,thread=multi,split-wx=on,tb-size=32",
            @"-smp",@"2",@"-m",@"512",@"-nodefaults",@"-display",@"egl-headless,gl=es",@"-chardev",
            [@"file,id=serial0,path=" stringByAppendingString:serial],@"-serial",@"chardev:serial0",@"-monitor",@"none",@"-kernel",
            [root stringByAppendingPathComponent:@"Image"],@"-initrd",[root stringByAppendingPathComponent:@"initramfs.cpio.gz"],@"-append",
            [@"console=ttyAMA0 rdinit=/init panic=1 virtio_gpu.mpc_native_display_fences=1 mpc_native_kms=1 mpc_run=" stringByAppendingString:nonce],
            @"-no-reboot",@"-device",@"virtio-gpu-gl-pci,blob=on,venus=on,hostmem=128M,xres=1280,yres=720",@"-d",@"guest_errors"];
        std::vector<std::string> values;for(NSString *s in arguments)values.emplace_back(s.UTF8String);
        double start=NSProcessInfo.processInfo.systemUptime;
        MPCDiagnosticStage(@"native-kms-before-engine-worker",@{@"run":nonce,@"uart_release_used":@NO});
        std::thread worker([values=std::move(values),init,loop,cleanup,bql,replay,retire]() mutable {
            int result=-999;MPCQEMUInitThreadLease lease(retire);
            @autoreleasepool {
                std::vector<char *> argv;for(auto &s:values)argv.push_back(s.data());argv.push_back(nullptr);
                MPCDiagnosticStage(@"native-kms-before-qemu-init",@{});init((int)argv.size()-1,argv.data());
                if(!lease.initializedOnThisThread())std::terminate();
                MPCDiagnosticStage(@"native-kms-qemu-init-returned",@{});MPCDetachJITDebugger();
                result=loop();MPCDiagnosticStage(@"native-kms-before-engine-cleanup",@{@"status":@(result)});
                cleanup(result);bql();replay();
            }
            @autoreleasepool {
                bool retired=lease.retire();rcuRetired.store(retired && lease.retired());
                MPCDiagnosticStage(@"native-kms-worker-retired",@{@"same_thread_rcu_retired":@(rcuRetired.load())});
            }
            status.store(result);finished.store(true);
        });
        while(!finished.load() && NSProcessInfo.processInfo.systemUptime-start<180)
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        bool done=finished.load();if(done)worker.join();else worker.detach();
        NSString *text=[NSString stringWithContentsOfFile:serial encoding:NSUTF8StringEncoding error:nil]?:@"";
        NSDictionary *native=MPCNativeDisplayCompletionReport();
        NSMutableDictionary *run=[MPCNativeKMSReceipt(text,nonce,native,done && rcuRetired.load() && status.load()==0) mutableCopy];
        if(done)run[@"guest_metal_trace"]=MPCGuestMetalTraceFinish([run[@"standard_kms_native_completion_verified"] isEqual:@YES]);
        BOOL passed=[run[@"standard_kms_native_completion_verified"] isEqual:@YES] &&
            [run[@"guest_metal_trace"][@"metal_host_verified"] isEqual:@YES];
        run[@"standard_kms_native_completion_verified"]=@(passed);
        run[@"status"]=passed?@"passed":done?@"failed":@"timed-out-engine-still-running";
        run[@"run"]=nonce;run[@"engine_finished"]=@(done);run[@"engine_worker_joined"]=@(done);
        run[@"engine_init_thread_rcu_unregistered"]=@(done && rcuRetired.load());run[@"engine_status"]=@(status.load());
        run[@"elapsed_ms"]=@((NSProcessInfo.processInfo.systemUptime-start)*1000);run[@"requires_relaunch"]=@YES;
        run[@"device"]=MPCPlatformFacts();run[@"payload"]=payload;run[@"engine_bundle"]=bundle;
        run[@"source_commit"]=[NSBundle.mainBundle objectForInfoDictionaryKey:@"MPCSourceCommit"]?:@"unknown";
        run[@"serial_output"]=text;run[@"hardware_virtualization"]=@NO;
        run[@"limitations"]=@"Eight immutable Linux images, standard atomic KMS output fences/events and actual native Metal completion. No UART releases or fixed dwell. QEMU TCG is software system emulation. Producer waits/readbacks are diagnostic; production compositor/WSI, desktop, ARM Steam, FEX, games, display timing and sustained performance remain unfinished. Timeout retains live work and cannot grant resource release.";
        NSData *data=[NSJSONSerialization dataWithJSONObject:run options:NSJSONWritingPrettyPrinted error:nil];
        [data writeToFile:[directory.path stringByAppendingPathComponent:@"linux-test.json"] atomically:YES];
        MPCDiagnosticStage(@"native-kms-result-saved",@{@"status":run[@"status"],@"verified":@(passed)});return run;
    }
}
