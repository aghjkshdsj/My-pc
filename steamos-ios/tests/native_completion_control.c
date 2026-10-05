/* SPDX-License-Identifier: MIT
 * Execute the actual adapter/ledger with a CPU executor shim, not Metal/QEMU.
 * The separate iOS job compiles the same adapter inside actual QEMU sources. */
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "../Engine/NativeCompletionABI.h"
typedef pthread_mutex_t QemuMutex;
typedef pthread_cond_t QemuCond;
typedef struct QEMUBH { void (*cb)(void *); void *context; } QEMUBH;
typedef struct VirtIOGPU { QEMUBH *cursor_bh; } VirtIOGPU;
static pthread_mutex_t test_bql = PTHREAD_MUTEX_INITIALIZER;
static _Thread_local bool test_has_bql;
static atomic_uint test_schedules, test_processed, test_destroyed;
static bool test_failed;
static inline bool bql_locked(void) { return test_has_bql; }
static inline void bql_lock(void) { pthread_mutex_lock(&test_bql); test_has_bql=true; }
static inline void bql_unlock(void) { test_has_bql=false; pthread_mutex_unlock(&test_bql); }
static inline void qemu_mutex_init(QemuMutex *m) { assert(!pthread_mutex_init(m,NULL)); }
static inline void qemu_mutex_lock(QemuMutex *m) { assert(!pthread_mutex_lock(m)); }
static inline void qemu_mutex_unlock(QemuMutex *m) { assert(!pthread_mutex_unlock(m)); }
static inline void qemu_cond_init(QemuCond *c) { assert(!pthread_cond_init(c,NULL)); }
static inline void qemu_cond_wait(QemuCond *c,QemuMutex *m) { assert(!pthread_cond_wait(c,m)); }
static inline void qemu_cond_broadcast(QemuCond *c) { assert(!pthread_cond_broadcast(c)); }
static QEMUBH *qemu_bh_new(void (*cb)(void *),void *p)
{ QEMUBH *b=malloc(sizeof(*b)); assert(b); *b=(QEMUBH){cb,p}; return b; }
static void qemu_bh_schedule(QEMUBH *b) { assert(b); atomic_fetch_add(&test_schedules,1); }
static void qemu_bh_delete(QEMUBH *b) { assert(bql_locked()); assert(b); free(b); }
static void virtio_gpu_process_cmdq(VirtIOGPU *);
static MPCNativeScanoutCallback mpc_scanout_callback;
static uint64_t mpc_scanout_sequence;
int mpc_qemu_cancel_native_read(const MPCNativeReadToken *);
#include "../Engine/QEMUNativeCompletion.inc"
static MPCNativeReadToken reads[16];
static unsigned read_count;
static int test_callback(void *context,const MPCNativeCompletionEvent *e)
{
    assert(context && e->abi==2 && e->bytes==sizeof(*e));
    if(e->image.kind==MPC_SCANOUT_FLUSH) {
        assert(read_count<16); reads[read_count++]=e->token;
    } else assert(!e->token.reader); /* Metadata never grants a read. */
    return 1;
}
static void virtio_gpu_process_cmdq(VirtIOGPU *g)
{
    assert(bql_locked());
    bool failed=false;
    assert(mpc_native_completion_finish(g,&failed));
    test_failed=failed; atomic_fetch_add(&test_processed,1);
}
static void emit(unsigned resource,unsigned generation)
{
    MPCNativeScanoutEvent e={.abi=1,.bytes=sizeof(e),.resource_id=resource,
        .generation=generation,.texture=(void *)(uintptr_t)0x1234};
    mpc_completion_emit(&e,MPC_SCANOUT_INSTALL);
    mpc_completion_emit(&e,MPC_SCANOUT_FLUSH);
}
static void *drain_thread(void *arg)
{
    bql_lock();mpc_native_completion_drain(arg);
    atomic_fetch_add(&test_destroyed,1);bql_unlock();return NULL;
}
static void short_pause(void)
{ struct timespec ts={.tv_nsec=20000000}; nanosleep(&ts,NULL); }
int main(void)
{
    QEMUBH cursor={0}; VirtIOGPU g={.cursor_bh=&cursor}; int context=1;
    assert(!mpc_qemu_configure_native_completion(1,sizeof(MPCNativeCompletionEvent),test_callback,&context));
    assert(mpc_qemu_configure_native_completion(2,sizeof(MPCNativeCompletionEvent),test_callback,&context));
    assert(!mpc_qemu_configure_native_completion(2,sizeof(MPCNativeCompletionEvent),test_callback,&context));
    bql_lock(); assert(mpc_native_completion_begin(&g));
    assert(!mpc_native_completion_begin(&g));
    for(unsigned i=0;i<3;i++) emit(42,100+i);
    mpc_native_completion_seal(3);
    bool failed=false;assert(!mpc_native_completion_finish(&g,&failed));bql_unlock();
    MPCNativeReadToken bad=reads[0];bad.session++;assert(!mpc_qemu_complete_native_read(&bad,4));
    bad=reads[0];bad.command++;assert(!mpc_qemu_complete_native_read(&bad,4));
    bad=reads[0];bad.generation++;assert(!mpc_qemu_complete_native_read(&bad,4));
    bad=reads[0];bad.resource_id++;assert(!mpc_qemu_complete_native_read(&bad,4));
    bad=reads[0];bad.reader++;assert(!mpc_qemu_complete_native_read(&bad,4));
    bad=reads[0];bad.reserved=1;assert(!mpc_qemu_complete_native_read(&bad,4));
    assert(!mpc_qemu_complete_native_read(&reads[0],3));
    assert(!mpc_qemu_complete_native_read(NULL,4));
    assert(mpc_qemu_complete_native_read(&reads[2],4));
    assert(!mpc_qemu_complete_native_read(&reads[2],4));
    assert(mpc_qemu_complete_native_read(&reads[0],5));
    assert(!atomic_load(&test_schedules));
    assert(mpc_qemu_complete_native_read(&reads[1],4));
    assert(atomic_load(&test_schedules)==1);
    bql_lock();mpc_completion_resume(&g);assert(test_failed);bql_unlock();
    assert(atomic_load(&test_processed)==1);
    assert(!mpc_qemu_complete_native_read(&reads[1],4));
    /* The last actual reader survives closing; there is no timeout release. */
    read_count=0;bql_lock();assert(mpc_native_completion_begin(&g));emit(42,200);
    mpc_native_completion_seal(1);bql_unlock();
    pthread_t drain;assert(!pthread_create(&drain,NULL,drain_thread,&g));
    bool closing=false;
    for(unsigned i=0;i<50 && !closing;i++) {
        short_pause();qemu_mutex_lock(&mpc_completion_mutex);
        closing=mpc_completion_join.closing;qemu_mutex_unlock(&mpc_completion_mutex);
    }
    assert(closing);
    for(unsigned i=0;i<5;i++) short_pause();
    assert(!atomic_load(&test_destroyed));
    unsigned schedules=atomic_load(&test_schedules);
    assert(mpc_qemu_complete_native_read(&reads[0],4));
    assert(!pthread_join(drain,NULL));
    assert(atomic_load(&test_destroyed)==1 && atomic_load(&test_schedules)==schedules);
    assert(!mpc_qemu_complete_native_read(&reads[0],4));
    /* New session may reuse a resource ID, never a stale read token. */
    MPCNativeReadToken stale=reads[0]; read_count=0;
    bql_lock();assert(mpc_native_completion_begin(&g));
    for(unsigned i=0;i<16;i++) emit(42,200+i);
    assert(!mpc_qemu_complete_native_read(&stale,4));
    MPCNativeScanoutEvent extra={.resource_id=42,.generation=300};
    mpc_completion_emit(&extra,MPC_SCANOUT_FLUSH);assert(read_count==16);
    mpc_native_completion_seal(16);bql_unlock();
    for(unsigned i=0;i<16;i++) assert(mpc_qemu_complete_native_read(&reads[15-i],4));
    bql_lock();mpc_completion_resume(&g);assert(test_failed);mpc_native_completion_drain(&g);bql_unlock();
    assert(atomic_load(&test_processed)==2);
    read_count=0;bql_lock();assert(mpc_native_completion_begin(&g));emit(42,400);
    mpc_native_completion_seal(1);bql_unlock();
    assert(!mpc_qemu_complete_native_read(&reads[0],MPC_NATIVE_READ_CANCELED));
    assert(mpc_qemu_cancel_native_read(&reads[0]));
    assert(!mpc_qemu_cancel_native_read(&reads[0]));
    bql_lock();mpc_completion_resume(&g);assert(test_failed);mpc_native_completion_drain(&g);bql_unlock();
    assert(atomic_load(&test_processed)==3);
    puts("MPC_NATIVE_COMPLETION_CPU_CONTROL passed: delayed/error/stale/duplicate/fanout/missing/drain/new-session/cancel-before-submission; Metal and actual QEMU runtime unverified");
    return 0;
}
