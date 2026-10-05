/* SPDX-License-Identifier: MIT
 * Bounded command join, serialized by the engine's adapter mutex. */
#ifndef MPC_NATIVE_COMPLETION_LEDGER_H
#define MPC_NATIVE_COMPLETION_LEDGER_H
#include <stdbool.h>
#include <string.h>
#include "NativeCompletionABI.h"
typedef struct MPCNativeCompletionLedger {
    uint64_t session, command, next_reader;
    MPCNativeReadToken tokens[MPC_NATIVE_MAX_READERS];
    uint32_t states[MPC_NATIVE_MAX_READERS], count, pending;
    bool active, sealed, failed, closing;
} MPCNativeCompletionLedger;
static inline bool mpc_join_begin(MPCNativeCompletionLedger *l, uint64_t command)
{
    if (l->active || l->closing || !command || !l->session) return false;
    l->command = command; l->count = l->pending = 0;
    l->active = true; l->sealed = l->failed = false;
    memset(l->states, 0, sizeof(l->states));
    return true;
}
static inline bool mpc_join_add(MPCNativeCompletionLedger *l,
    uint32_t resource, uint64_t generation, MPCNativeReadToken *out)
{
    if (!l->active || l->sealed || l->closing || !resource || !generation ||
        l->count == MPC_NATIVE_MAX_READERS || l->next_reader == UINT64_MAX) {
        l->failed = true; return false;
    }
    *out = (MPCNativeReadToken) {l->session, l->command, ++l->next_reader,
                               generation, resource, 0};
    l->tokens[l->count++] = *out; l->pending++;
    return true;
}
static inline bool mpc_join_complete(MPCNativeCompletionLedger *l,
    const MPCNativeReadToken *t, uint32_t status)
{
    if (!t || !l->active || (status != MPC_NATIVE_READ_COMPLETED &&
        status != MPC_NATIVE_READ_ERROR) || t->reserved ||
        t->session != l->session || t->command != l->command) return false;
    for (uint32_t i = 0; i < l->count; i++) {
        const MPCNativeReadToken *x = &l->tokens[i];
        if (x->reader == t->reader && x->generation == t->generation &&
            x->resource_id == t->resource_id && !l->states[i]) {
            l->states[i] = status; l->pending--;
            l->failed |= status == MPC_NATIVE_READ_ERROR; return true;
        }
    }
    return false;
}
static inline bool mpc_join_ready(const MPCNativeCompletionLedger *l)
{ return l->active && l->sealed && !l->pending; }
static inline bool mpc_join_retire(MPCNativeCompletionLedger *l)
{
    if (!mpc_join_ready(l)) return false;
    l->active = false; return true;
}
#endif
