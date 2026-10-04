#import <Foundation/Foundation.h>
BOOL MPCGuestFrameImportBegin(NSString *nonce, void *engine, NSError **error);
NSDictionary *MPCGuestFrameImportFinish(NSString *serial, BOOL engineFinished, BOOL linuxPassed, BOOL guestMetalPassed);
NSDictionary *MPCValidateGuestFrameImport(NSString *serial, NSString *nonce, NSDictionary *native, BOOL engineFinished, BOOL linuxPassed, BOOL guestMetalPassed);
NSDictionary *MPCValidateGuestFrameScreen(NSString *nonce, NSDictionary *imported, NSDictionary *native, BOOL engineFinished);
