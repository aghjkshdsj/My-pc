/* Bounded schedule and endpoint byte-order checks, MIT. No GPU rendering. */
#include "../Engine/MovingFrameContract.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
static uint64_t checks;
#define CHECK(v) do { ++checks; if (!(v)) { fprintf(stderr,"moving pixel check line=%d\n",__LINE__); exit(1); } } while(0)
int main(void) {
    unsigned seen[120]={0},uses[3]={0},endpoints=0;
    uint64_t sum=0,pixels=0;
    for (unsigned i=0;i<MPC_MOVING_FRAMES;++i) {
        unsigned phase=mpc_moving_phase(i);
        CHECK(phase<120 && !seen[phase]);seen[phase]=1;uses[i%3]++;
        if (!mpc_moving_endpoint(i)) continue;
        ++endpoints;
        for (unsigned y=0;y<720;++y) for (unsigned x=0;x<1280;++x) {
            unsigned char p[4]={(unsigned char)(165u^phase),(unsigned char)((y+phase)&255u),
                                (unsigned char)((x+phase)&255u),255};
            CHECK(mpc_moving_pattern_matches(p,x,y,phase,1));
            for (unsigned c=0;c<4;++c) sum+=p[c];
            ++pixels;
        }
    }
    CHECK(endpoints==2 && uses[0]==40 && uses[1]==40 && uses[2]==40);
    CHECK(mpc_moving_phase(120)==999);
    unsigned char bad[4]={165,0,0,254};CHECK(!mpc_moving_pattern_matches(bad,0,0,0,1));
    printf("{\"checks\":%" PRIu64 ",\"endpoint_pixels\":%" PRIu64 ",\"channel_sum\":%" PRIu64
           ",\"distinct_phases\":120,\"fixed_resources\":3,\"rendered_gpu_frames\":0}\n",checks,pixels,sum);
    return 0;
}
