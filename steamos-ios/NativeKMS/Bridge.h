#import "../Host/ProbeBridge.h"
NS_ASSUME_NONNULL_BEGIN
#ifdef __cplusplus
extern "C" {
#endif
UIView *MPCNativeKMSCreateView(void);
NSDictionary *MPCNativeKMSRun(void);
NSDictionary *MPCNativeKMSReceipt(NSString *serial, NSString *nonce, NSDictionary *native, BOOL retired);
#ifdef __cplusplus
}
#endif
NS_ASSUME_NONNULL_END
