/* SPDX-License-Identifier: GPL-2.0-or-later
 * Included in the separately patched QEMU egl-headless backend. */
#include "qemu/main-loop.h"
#include "qemu/thread.h"
#include "system/bql.h"
#include "hw/virtio/virtio-gpu.h"
#include "ui/mpc-native-completion-ledger.h"
static MPCNativeCompletionCallback mpc_completion_callback;
static void *mpc_completion_context;
static QemuMutex mpc_completion_mutex;
static QemuCond mpc_completion_cond;
static MPCNativeCompletionLedger mpc_completion_join = { .session = 1 };
static VirtIOGPU *mpc_completion_owner;
static QEMUBH *mpc_completion_bh;
static uint64_t mpc_completion_command;

static void mpc_completion_resume(void *opaque)
{
    VirtIOGPU *g = opaque;
    bool ready;
    assert(bql_locked());
    qemu_mutex_lock(&mpc_completion_mutex);
    ready = mpc_completion_owner == g &&
            !mpc_completion_join.closing && mpc_join_ready(&mpc_completion_join);
    qemu_mutex_unlock(&mpc_completion_mutex);
    if (ready) {
        /* This is the owned QEMU executor. Metal callbacks never run GL. */
        virtio_gpu_process_cmdq(g);
        qemu_bh_schedule(g->cursor_bh);
    }
}
__attribute__((visibility("default")))
int mpc_qemu_configure_native_completion(uint32_t abi, uint32_t bytes,
    MPCNativeCompletionCallback callback, void *context)
{
    if (abi != MPC_NATIVE_COMPLETION_ABI || bytes != sizeof(MPCNativeCompletionEvent) ||
        !callback || !context || mpc_completion_callback || mpc_scanout_callback ||
        mpc_scanout_sequence) return 0;
    qemu_mutex_init(&mpc_completion_mutex);
    qemu_cond_init(&mpc_completion_cond);
    mpc_completion_context = context;
    mpc_completion_callback = callback;
    return 1;
}
__attribute__((visibility("default")))
int mpc_qemu_complete_native_read(const MPCNativeReadToken *token, uint32_t status)
{
    bool accepted;
    if (!mpc_completion_callback) return 0;
    qemu_mutex_lock(&mpc_completion_mutex);
    accepted = mpc_join_complete(&mpc_completion_join, token, status);
    if (accepted && !mpc_completion_join.pending) {
        qemu_cond_broadcast(&mpc_completion_cond);
        if (!mpc_completion_join.closing && mpc_completion_bh &&
            mpc_join_ready(&mpc_completion_join)) qemu_bh_schedule(mpc_completion_bh);
    }
    qemu_mutex_unlock(&mpc_completion_mutex);
    return accepted;
}
bool mpc_native_completion_enabled(void) { return mpc_completion_callback != NULL; }
bool mpc_native_completion_busy(VirtIOGPU *g)
{
    bool busy;
    if (!mpc_completion_callback) return false;
    qemu_mutex_lock(&mpc_completion_mutex);
    busy = mpc_completion_owner == g && mpc_completion_join.active;
    qemu_mutex_unlock(&mpc_completion_mutex);
    return busy;
}
bool mpc_native_completion_begin(VirtIOGPU *g)
{
    bool ok;
    assert(bql_locked());
    qemu_mutex_lock(&mpc_completion_mutex);
    ok = (!mpc_completion_owner || mpc_completion_owner == g) &&
         mpc_completion_command != UINT64_MAX &&
         mpc_join_begin(&mpc_completion_join, ++mpc_completion_command);
    if (ok && !mpc_completion_bh) {
        mpc_completion_bh = qemu_bh_new(mpc_completion_resume, g);
        mpc_completion_owner = g;
    }
    qemu_mutex_unlock(&mpc_completion_mutex);
    return ok;
}
static void mpc_completion_emit(MPCNativeScanoutEvent *image, uint32_t kind)
{
    MPCNativeCompletionEvent e = { .abi = MPC_NATIVE_COMPLETION_ABI,
        .bytes = sizeof(e), .image = *image };
    e.image.kind = kind;
    if (kind == MPC_SCANOUT_FLUSH) {
        qemu_mutex_lock(&mpc_completion_mutex);
        bool ok = mpc_join_add(&mpc_completion_join, image->resource_id,
                               image->generation, &e.token);
        qemu_mutex_unlock(&mpc_completion_mutex);
        if (!ok) return; /* Fail the command, submit no untracked read. */
        if (!mpc_completion_callback(mpc_completion_context, &e)) {
            /* Rejection means the host submitted NO read. */
            mpc_qemu_complete_native_read(&e.token, MPC_NATIVE_READ_ERROR);
        }
    } else {
        mpc_completion_callback(mpc_completion_context, &e);
    }
}
void mpc_native_completion_seal(uint32_t expected)
{
    qemu_mutex_lock(&mpc_completion_mutex);
    mpc_completion_join.failed |= expected != mpc_completion_join.count;
    mpc_completion_join.sealed = true;
    qemu_mutex_unlock(&mpc_completion_mutex);
}
bool mpc_native_completion_finish(VirtIOGPU *g, bool *failed)
{
    bool ready;
    qemu_mutex_lock(&mpc_completion_mutex);
    ready = mpc_completion_owner == g && mpc_join_ready(&mpc_completion_join);
    if (ready) {
        *failed = mpc_completion_join.failed;
        mpc_join_retire(&mpc_completion_join);
    }
    qemu_mutex_unlock(&mpc_completion_mutex);
    return ready;
}
void mpc_native_completion_drain(VirtIOGPU *g)
{
    if (!mpc_completion_callback) return;
    assert(bql_locked());
    qemu_mutex_lock(&mpc_completion_mutex);
    if (mpc_completion_owner == g) {
        mpc_completion_join.closing = true;
        while (mpc_completion_join.pending) {
            /* No teardown deadline. Release BQL while waiting for actual
             * terminal GPU callbacks; reacquire without reversing lock order. */
            bql_unlock();
            qemu_cond_wait(&mpc_completion_cond, &mpc_completion_mutex);
            qemu_mutex_unlock(&mpc_completion_mutex);
            bql_lock();
            qemu_mutex_lock(&mpc_completion_mutex);
        }
        qemu_bh_delete(mpc_completion_bh);
        mpc_completion_bh = NULL; mpc_completion_owner = NULL;
        mpc_completion_join.active = false;
        /* Session is never recycled. Exhaustion permanently closes adapter. */
        if (mpc_completion_join.session != UINT64_MAX) {
            mpc_completion_join.session++;
            mpc_completion_join.closing = false;
        }
    }
    qemu_mutex_unlock(&mpc_completion_mutex);
}
