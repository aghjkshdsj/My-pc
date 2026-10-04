#include "../Engine/FrameSequenceContract.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    const uint64_t sums[MPC_FRAME_COUNT] = {615690240,634040320,597094400,614461440,
        682536960,695316480,652800000,665579520};
    uint64_t total = 0;
    for (unsigned i=0; i<MPC_FRAME_COUNT; ++i) {
        unsigned phase=mpc_frame_phase(i); uint64_t sum=0;
        for (unsigned y=0; y<720; ++y) for (unsigned x=0; x<1280; ++x) {
            unsigned char p[] = {(165^phase)&255,(y+phase)&255,(x+phase)&255,255};
            if (!mpc_frame_pattern_matches(p,x,y,phase,1)) abort();
            if (mpc_frame_pattern_matches(p,x,y,mpc_frame_phase((i+1)%MPC_FRAME_COUNT),1)) abort();
            sum+=p[0]+p[1]+p[2]+p[3];
        }
        if (sum!=sums[i]) abort();
        total+=sum;
    }
    unsigned char p[]={165,0,0,255};
    if (mpc_frame_phase(8)!=999 || mpc_frame_pattern_matches(p,0,0,999,1) ||
        mpc_frame_pattern_matches(p,0,0,41,1) || total!=UINT64_C(5157519360)) abort();
    printf("FRAME_PIXEL_CONTRACT_OK pixels=7372800 channel_sum=%" PRIu64 " scope=synthetic-only\n",total);
}
