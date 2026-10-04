/* Fresh adapter, MIT. A borrowed texture is valid only during its callback. */
#ifndef MPC_NATIVE_SCANOUT_ABI_H
#define MPC_NATIVE_SCANOUT_ABI_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { MPC_SCANOUT_ABI = 1, MPC_SCANOUT_INSTALL = 1,
       MPC_SCANOUT_FLUSH = 2, MPC_SCANOUT_DISABLE = 3 };
typedef struct MPCNativeScanoutEvent {
    uint32_t abi, bytes, kind, resource_id;
    uint64_t sequence, generation;
    uint32_t width, height, format, stride, offset;
    uint32_t x, y, crop_width, crop_height, y_0_top;
    void *texture;
} MPCNativeScanoutEvent;
typedef void (*MPCNativeScanoutCallback)(void *, const MPCNativeScanoutEvent *);
typedef int (*MPCConfigureNativeScanout)(uint32_t, uint32_t,
                                        MPCNativeScanoutCallback, void *);
int mpc_qemu_configure_native_scanout(uint32_t, uint32_t,
                                    MPCNativeScanoutCallback, void *);
#ifdef __cplusplus
}
#endif
#endif
