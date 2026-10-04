/* Exercise the production budget decision with synthetic events, MIT. */
#include <assert.h>
#include <stdio.h>
#include "../Host/GuestImageReadbackBudget.h"
static MPCNativeScanoutEvent event(unsigned resource, unsigned generation, unsigned sequence) {
    return (MPCNativeScanoutEvent){.abi=1,.bytes=sizeof(MPCNativeScanoutEvent),.kind=MPC_SCANOUT_FLUSH,
        .resource_id=resource,.generation=generation,.sequence=sequence,.width=1280,.height=720,
        .format=2,.stride=5120,.crop_width=1280,.crop_height=720,.texture=(void *)1};
}
int main(void) {
    MPCImageReadbackBudget budget = {0};
    MPCNativeScanoutEvent first=event(12,1,2), reinstall=event(12,2,5), second=event(19,3,8), repeat=event(19,3,9);
    assert(mpc_reserve_image_readback(&budget,&first)==MPC_IMAGE_BUDGET_CONSUME);
    assert(budget.count==1 && !budget.resources[0].texture);
    assert(mpc_reserve_image_readback(&budget,&reinstall)==MPC_IMAGE_BUDGET_REPEAT && budget.count==1);
    assert(mpc_reserve_image_readback(&budget,&second)==MPC_IMAGE_BUDGET_CONSUME && budget.count==2);
    assert(mpc_reserve_image_readback(&budget,&repeat)==MPC_IMAGE_BUDGET_REPEAT && budget.count==2);
    MPCNativeScanoutEvent third=event(25,4,11);
    assert(mpc_reserve_image_readback(&budget,&third)==MPC_IMAGE_BUDGET_REJECT && budget.count==2);
    unsigned rejections=0;
    for (unsigned i=0;i<13;++i) {
        MPCNativeScanoutEvent bad=reinstall;
        switch(i) {
        case 0: bad.offset=512;break; case 1: bad.stride=10240;break; case 2: bad.format=67;break;
        case 3: bad.width=640;break; case 4: bad.height=480;break; case 5: bad.x=1;break;
        case 6: bad.y=1;break; case 7: bad.crop_width=640;break; case 8: bad.crop_height=480;break;
        case 9: bad.y_0_top=1;break; case 10: bad.texture=0;break; case 11: bad.resource_id=0;break;
        default: bad.kind=MPC_SCANOUT_INSTALL;break;
        }
        assert(mpc_reserve_image_readback(&budget,&bad)==MPC_IMAGE_BUDGET_REJECT && budget.count==2);rejections++;
    }
    assert(mpc_reserve_image_readback(&budget,0)==MPC_IMAGE_BUDGET_REJECT);rejections++;
    printf("IMAGE_READBACK_BUDGET_OK distinct_resources=2 repeated_callbacks=2 rejections=%u; synthetic fixtures only\n",rejections);
    return 0;
}
