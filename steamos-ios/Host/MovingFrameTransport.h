// Fresh MIT diagnostic UART release bridge. Production KMS/WSI is separate.
#import <Foundation/Foundation.h>
BOOL MPCMovingTransportBegin(NSString *nonce, void *engine, NSString *serialPath, NSError **error);
int MPCMovingTransportEngineFD(void);
void MPCMovingTransportTransferEngineFD(void);
void MPCMovingTransportJoinReader(BOOL engineFinished);
NSDictionary *MPCMovingTransportFinish(NSString *serial, BOOL engineFinished, BOOL linuxPassed, BOOL metalPassed);
NSDictionary *MPCValidateMovingFrames(NSString *serial, NSString *nonce, NSDictionary *native,
    NSDictionary *screen, BOOL engineFinished, BOOL linuxPassed, BOOL metalPassed);
