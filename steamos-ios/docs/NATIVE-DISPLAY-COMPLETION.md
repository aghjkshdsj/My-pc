# Native display completion fork

This separate engine variant connects the new Linux display response contract
to an asynchronous native reader interface. It does not replace the accepted
build 4000027 engine, image payload or iPhone results. No new IPA is ready yet.

## Implemented source

ABI2 configuration is exclusive with the existing ABI1 callback. INSTALL and
DISABLE carry metadata only. Each FLUSH reader has a session, command, reader,
resource and installation-generation token. The host must immediately retain
the borrowed texture/backing before returning acceptance. It must submit no GPU
read if it rejects the event. Only actual GPU Completed/Error can return a
ticket; CPU deadlines and display presentation times cannot return ownership.

The exact RESOURCE_FLUSH remains suspended at the owned QEMU command-queue
head, outside the renderer fence queue. Up to 16 matching native readers join.
Only when every accepted reader is terminal does the owned engine bottom half
resume that command, without issuing its display flush twice. Then its renderer
fence can retire. A failed native read or renderer fence fails the command.
An unsupported native scanout cannot silently fall back to successful readback.
Unrelated renderer fence watermarks never see the suspended display command.

Cursor queue processing pauses during a native transaction. Reset, scanout reset
and device unrealize drain actual readers before destroying their resources or
renderer. A missing terminal callback retains ownership and can therefore leave
shutdown waiting indefinitely; this is a deliberate conservative failure state,
not a completed shutdown. Closing suppresses queue-resume callbacks. After drain,
the engine deletes the bottom half and advances its session; stale and duplicate
completions are rejected. The callback context and adapter synchronization live
for the engine library's process lifetime. Reconfiguration is unsupported.

## Validation boundaries

The patcher verifies six complete pinned upstream-plus-adapter input hashes
before writing. Separate corresponding source includes original engine archives,
upstream patches and notices, the fresh patch/templates, actual modified sources,
recipes, configurations, build audits and controls. QEMU modifications are
GPL-2.0-or-later; the standalone ABI/ledger and CPU control are MIT. This reuses
the QEMU engine and graphics engines, not the upstream application's app base.

The CPU control executes the actual adapter and ledger using a small executor
shim. It checks delayed fanout, errors, malformed/stale/duplicate tickets,
over-capacity rejection, a genuinely blocked drain and a new session. Normal
and address/undefined-sanitizer runs are required on the hosted iOS build runner.
They do not execute actual QEMU queues or Metal. The separate hosted build must
also compile the modified real QEMU sources for device ARM64 iOS and audit its
defined exports, compiled translation units and exact patched source hashes.

## Remaining work

1. Connect a bounded generic host consumer to ABI2. Retain texture/backing through
   actual Metal terminal callbacks; report command errors; never wait for GPU on
   the main thread. Keep CPU-copy diagnostics separate.
2. Join actual guest Vulkan/WSI producer dependencies before the host samples the
   image. The source's renderer completion plus native completion join does not
   establish that cross-queue producer visibility or ordering is correct.
3. Pair the separately tested Linux completion kernel with this engine and a
   standard DRM/Vulkan display producer, then measure the complete joined path
   on the actual iPhone. Exercise disable, reset, missing/error response and
   repeated resource reuse on that path. Hardware cursor reads remain unfinished.
4. Move to a real compositor and authenticated compatible Valve runtime. Desktop,
   ARM Steam, FEX/Proton, games and product performance targets remain unfinished.

QEMU TCG here remains software system emulation. FEX is x86 instruction
translation; Proton is Windows compatibility. No hypervisor is added or claimed.
