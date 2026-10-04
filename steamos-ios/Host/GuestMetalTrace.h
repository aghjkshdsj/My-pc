#import <Foundation/Foundation.h>
BOOL MPCGuestMetalTraceBegin(NSString *run, NSString *framework, NSError **error);
NSDictionary *MPCGuestMetalTraceFinish(BOOL guestPixelsPassed);
