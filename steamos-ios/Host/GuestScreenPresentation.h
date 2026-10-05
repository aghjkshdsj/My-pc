#import <Foundation/Foundation.h>
#include "../Engine/NativeScanoutABI.h"
BOOL MPCGuestFrameScreenBegin(NSString *nonce, NSError **error);
BOOL MPCGuestScreenBegin(NSString *nonce, NSError **error);
BOOL MPCGuestMovingScreenBegin(NSString *nonce, NSError **error);
NSDictionary *MPCGuestMovingScreenConsume(const MPCNativeScanoutEvent *event, NSDictionary *verifiedImage,
    BOOL (^willSubmit)(void), void (^completed)(uint32_t, BOOL));
NSDictionary *MPCGuestMovingScreenSnapshot(void);
NSDictionary *MPCGuestScreenConsume(const MPCNativeScanoutEvent *event, NSDictionary *verifiedImage);
NSDictionary *MPCGuestScreenFinish(NSDictionary *imageImport, BOOL engineFinished);
NSDictionary *MPCValidateGuestScreen(NSString *nonce, NSDictionary *imageImport,
                                     NSDictionary *native, BOOL engineFinished);
