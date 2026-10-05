/* Exercise actual encoding and rejection, not a phone/GPU fixture. MIT. */
#include "../Engine/FrameReleaseWire.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned checks;
#define CHECK(v) do { ++checks; if (!(v)) { fprintf(stderr,"wire check failed line=%d\n",__LINE__); exit(1); } } while(0)
int main(void) {
    MPCReleaseMessage original = {UINT64_C(0x0123456789abcdef), UINT64_C(0xfedcba9876543210),
        UINT64_C(0x1020304050607080), 1, 3, 99, 7, 4, MPC_RELEASE_COMPLETED}, decoded = {0};
    unsigned char bytes[MPC_RELEASE_WIRE_BYTES], changed[MPC_RELEASE_WIRE_BYTES];
    CHECK(mpc_wire_encode(&original,bytes,sizeof(bytes)));
    CHECK(mpc_wire_decode(bytes,sizeof(bytes),&decoded) && mpc_wire_identity(&decoded,&original));
    CHECK(decoded.registry==99 && decoded.release==3 && decoded.code==4);
    CHECK(bytes[0]=='M' && bytes[1]=='P' && bytes[2]=='C' && bytes[3]=='R');
    CHECK(mpc_wire_crc((const unsigned char *)"123456789",9)==UINT32_C(0xcbf43926));
    for (unsigned bit=0;bit<sizeof(bytes)*8;++bit) {
        memcpy(changed,bytes,sizeof(bytes));changed[bit/8]^=(unsigned char)(1u<<(bit%8));
        CHECK(!mpc_wire_decode(changed,sizeof(changed),&decoded));
    }
    CHECK(!mpc_wire_decode(bytes,sizeof(bytes)-1,&decoded));
    CHECK(!mpc_wire_encode(&original,bytes,sizeof(bytes)-1));
    CHECK(!mpc_wire_session("00000000000000000000000000000000",&decoded.session_high,&decoded.session_low));
    CHECK(!mpc_wire_session("0123456789ABCDEFfedcba9876543210",&decoded.session_high,&decoded.session_low));
    CHECK(mpc_wire_session("0123456789abcdeffedcba9876543210",&decoded.session_high,&decoded.session_low));
    CHECK(decoded.session_high==original.session_high && decoded.session_low==original.session_low);
    decoded=original;decoded.serial++;CHECK(!mpc_wire_identity(&decoded,&original));
    decoded=original;decoded.session_low++;CHECK(!mpc_wire_identity(&decoded,&original));
    decoded=original;decoded.resource++;CHECK(!mpc_wire_identity(&decoded,&original));
    decoded=original;decoded.incarnation++;CHECK(!mpc_wire_identity(&decoded,&original));
    decoded=original;decoded.kind++;CHECK(!mpc_wire_identity(&decoded,&original));
    printf("RELEASE_WIRE_OK checks=%u altered_bits_rejected=640 gpu_verified=0\n",checks);
    return 0;
}
