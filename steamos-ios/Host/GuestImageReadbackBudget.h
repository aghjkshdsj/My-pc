/* Bounded immutable-resource diagnostic readbacks, MIT. No GPU work here. */
#ifndef MPC_GUEST_IMAGE_READBACK_BUDGET_H
#define MPC_GUEST_IMAGE_READBACK_BUDGET_H
#include "../Engine/NativeScanoutABI.h"
#include "../Engine/ImagePixelContract.h"
enum { MPC_IMAGE_BUDGET_REJECT = -1, MPC_IMAGE_BUDGET_CONSUME = 1, MPC_IMAGE_BUDGET_REPEAT = 2 };
typedef struct MPCImageReadbackBudget {
    MPCNativeScanoutEvent resources[2];
    unsigned count;
} MPCImageReadbackBudget;
static inline int mpc_reserve_image_readback(MPCImageReadbackBudget *budget,
                                            const MPCNativeScanoutEvent *event) {
    if (!budget || !event || budget->count > 2 || !event->texture || !event->resource_id ||
        event->kind != MPC_SCANOUT_FLUSH || !event->generation || !event->sequence ||
        event->width != 1280 || event->height != 720 || event->format != MPC_IMAGE_VIRTIO_BGRX8 ||
        event->stride < 5120 || event->stride > (1u << 24) || event->x || event->y ||
        event->crop_width != 1280 || event->crop_height != 720 || event->y_0_top)
        return MPC_IMAGE_BUDGET_REJECT;
    for (unsigned i = 0; i < budget->count; ++i) {
        const MPCNativeScanoutEvent *old = &budget->resources[i];
        if (old->resource_id != event->resource_id) continue;
        /* A reinstalled immutable resource is the same image, even with a new
         * native generation/texture wrapper. Refuse altered layout/format. */
        if (old->width != event->width || old->height != event->height || old->format != event->format ||
            old->stride != event->stride || old->offset != event->offset || old->x != event->x ||
            old->y != event->y || old->crop_width != event->crop_width || old->crop_height != event->crop_height ||
            old->y_0_top != event->y_0_top) return MPC_IMAGE_BUDGET_REJECT;
        return MPC_IMAGE_BUDGET_REPEAT;
    }
    if (budget->count == 2) return MPC_IMAGE_BUDGET_REJECT;
    budget->resources[budget->count++] = *event;
    /* Never retain or later dereference the callback's borrowed texture. */
    budget->resources[budget->count - 1].texture = 0;
    return MPC_IMAGE_BUDGET_CONSUME;
}
#endif
