#import <Foundation/Foundation.h>
BOOL MPCGuestImageImportBegin(NSString *nonce, void *engine, NSError **error);
NSDictionary *MPCGuestImageImportFinish(NSString *serial, BOOL engineFinished,
                                      BOOL linuxPassed, BOOL guestMetalPassed);
NSDictionary *MPCValidateGuestImageImport(NSString *serial, NSString *nonce,
    NSDictionary *native, BOOL engineFinished, BOOL linuxPassed, BOOL guestMetalPassed);
