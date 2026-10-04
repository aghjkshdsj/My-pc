#import <Foundation/Foundation.h>
@class UIView;

NS_ASSUME_NONNULL_BEGIN
#ifdef __cplusplus
extern "C" {
#endif
NSDictionary *MPCPlatformFacts(void);
NSDictionary *MPCExecuteJITProbe(void);
NSDictionary *MPCMetalProbe(void);
NSDictionary *MPCStorageProbe(void);
NSDictionary *MPCLinuxKernelProbe(void);
NSDictionary *MPCLinuxGuestGPUProbe(void);
NSDictionary *MPCLinuxGuestImageProbe(void);
NSDictionary *MPCLinuxGuestScreenProbe(void);
NSDictionary *MPCLinuxGuestFrameProbe(void);
UIView *MPCGuestScreenCreateView(void);
NSDictionary *MPCParseGuestGPUReceipt(NSString *text, NSString *nonce, BOOL linuxPassed);
NSDictionary * _Nullable MPCFrameworkTextIdentity(NSString *path);
NSDictionary *MPCNativeCPUProbe(void);
NSDictionary *MPCNativeVulkanProbe(NSString *diagnosticDirectory);
BOOL MPCStartDiagnosticCapture(NSString *directory);
BOOL MPCDiagnosticStage(NSString *stage, NSDictionary *details);
void MPCStopDiagnosticCapture(void);
NSDictionary *MPCDiagnosticOutputSnapshot(NSString *directory);
BOOL MPCDetachJITDebugger(void);
BOOL MPCConfigureQEMUJIT(void);
#ifdef __cplusplus
}
#endif
NS_ASSUME_NONNULL_END
