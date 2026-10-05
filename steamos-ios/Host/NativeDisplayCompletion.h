/* SPDX-License-Identifier: MIT */
#import <Foundation/Foundation.h>
@class CAMetalLayer;
#ifdef __cplusplus
extern "C" {
#endif
/* Configure before engine initialization. The caller owns a stable, visible
 * pure-Metal layer (presentsWithTransaction=NO) and keeps the engine loaded for
 * process lifetime. This is separate from the accepted UART-driven preview. */
BOOL MPCNativeDisplayCompletionBegin(void *engine, CAMetalLayer *layer, NSError **error);
NSDictionary *MPCNativeDisplayCompletionReport(void);
#ifdef __cplusplus
}
#endif
