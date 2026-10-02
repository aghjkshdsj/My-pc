#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN
#ifdef __cplusplus
extern "C" {
#endif
NSDictionary *MPCPlatformFacts(void);
NSDictionary *MPCExecuteJITProbe(void);
NSDictionary *MPCMetalProbe(void);
NSDictionary *MPCStorageProbe(void);
NSDictionary *MPCLinuxKernelProbe(void);
#ifdef __cplusplus
}
#endif
NS_ASSUME_NONNULL_END
