/* SPDX-License-Identifier: MIT */
#ifndef MPC_NATIVE_COMPLETION_ABI_H
#define MPC_NATIVE_COMPLETION_ABI_H
#include <stdint.h>
#include <stdbool.h>
#include "NativeScanoutABI.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { MPC_NATIVE_COMPLETION_ABI = 2, MPC_NATIVE_READ_COMPLETED = 4,
       MPC_NATIVE_READ_ERROR = 5, MPC_NATIVE_MAX_READERS = 16 };
typedef struct MPCNativeReadToken {
    uint64_t session, command, reader, generation;
    uint32_t resource_id, reserved;
} MPCNativeReadToken;
typedef struct MPCNativeCompletionEvent {
    uint32_t abi, bytes;
    MPCNativeScanoutEvent image;
    MPCNativeReadToken token;
} MPCNativeCompletionEvent;
/* INSTALL/DISABLE are metadata only: they MUST NOT submit GPU reads.
 * FLUSH has one token per actual reader. Return 1 only after retaining the
 * borrowed texture/backing and accepting responsibility for exactly one
 * terminal completion. Return 0 only if no read was submitted. A timeout,
 * drawable presentation callback, or CPU copy is NOT a terminal GPU result.
 * No call into the engine executor from this callback. */
typedef int (*MPCNativeCompletionCallback)(void *, const MPCNativeCompletionEvent *);
typedef int (*MPCConfigureNativeCompletion)(uint32_t, uint32_t,
    MPCNativeCompletionCallback, void *);
/* Thread safe; only actual MTLCommandBufferStatusCompleted/Error are valid.
 * An error is terminal for ownership but fails the Linux display command.
 * Returns 0 for invalid, stale or duplicate tokens. Missing completions retain
 * ownership indefinitely, including during reset/shutdown. */
typedef int (*MPCCompleteNativeRead)(const MPCNativeReadToken *, uint32_t);
#ifdef __cplusplus
}
#endif
#endif
