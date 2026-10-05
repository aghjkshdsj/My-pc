/* Actual Linux UART binary-response gate, MIT. It does not execute a GPU. */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include "frame_release_channel.h"
int main(void) {
    const char *nonce = getenv("MPC_CHANNEL_RUN");
    MPCReleaseMessage expected = {0}, received = {0};
    if (!mpc_wire_session(nonce, &expected.session_high, &expected.session_low)) return 2;
    expected.kind = MPC_RELEASE_CHANNEL_PROBE; expected.serial = 1; expected.incarnation = 1; expected.resource = 7;
    MPCGuestChannel channel = {.fd = -1};
    if (!mpc_channel_open(&channel)) return 3;
    printf("MPC_CHANNEL_REQUEST {\"schema\":1,\"run\":\"%s\",\"serial\":1,\"incarnation\":1,\"resource_id\":7}\n", nonce);
    fflush(stdout);
    int passed = mpc_channel_receive(&channel, &expected, &received, 5000) && received.code == 0 &&
                 received.release == 0 && received.registry == 0;
    mpc_channel_close(&channel);
    printf("MPC_CHANNEL_RESULT {\"schema\":1,\"run\":\"%s\",\"binary_response_verified\":%s,"
           "\"native_gpu_verified\":false,\"buffer_reuse_verified\":false}\n", nonce, passed ? "true" : "false");
    return passed ? 0 : 4;
}
