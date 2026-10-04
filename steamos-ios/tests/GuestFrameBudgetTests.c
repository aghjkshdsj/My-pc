/* Production eight-resource budget rejection fixtures, MIT. */
#include <assert.h>
#include <stdio.h>
#include "../Host/GuestFrameBudget.h"
int main(void) {
    MPCFrameBudget budget={0};
    for(unsigned i=0;i<8;i++) {
        MPCNativeScanoutEvent e={.kind=2,.resource_id=i+10,.generation=i+1,.sequence=i*3+2,
            .width=1280,.height=720,.format=2,.stride=5120,.crop_width=1280,.crop_height=720,.texture=(void *)1};
        assert(mpc_reserve_frame(&budget,&e)==MPC_FRAME_BUDGET_CONSUME);
        assert(budget.count==i+1 && !budget.resources[i].texture);
        e.generation+=100; e.sequence+=100;
        assert(mpc_reserve_frame(&budget,&e)==MPC_FRAME_BUDGET_REPEAT);
        e.offset=256;
        assert(mpc_reserve_frame(&budget,&e)==MPC_FRAME_BUDGET_REJECT);
        e=budget.resources[i];e.texture=(void *)1;e.resource_id=99;
        if(i==7) assert(mpc_reserve_frame(&budget,&e)==MPC_FRAME_BUDGET_REJECT);
    }
    printf("FRAME_BUDGET_OK eight immutable resources; duplicates skipped; altered layout and ninth rejected; synthetic-only\n");
}
