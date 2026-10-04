#import <Foundation/Foundation.h>
#include "../Engine/NativeScanoutABI.h"
BOOL MPCGuestScreenBegin(NSString *nonce, NSError **error);
NSDictionary *MPCGuestScreenConsume(const MPCNativeScanoutEvent *event, NSDictionary *verifiedImage);
NSDictionary *MPCGuestScreenFinish(NSDictionary *imageImport, BOOL engineFinished);
NSDictionary *MPCValidateGuestScreen(NSString *nonce, NSDictionary *imageImport,
                                     NSDictionary *native, BOOL engineFinished);
