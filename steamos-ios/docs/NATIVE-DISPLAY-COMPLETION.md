# Native display completion fork

This separate engine variant connects the new Linux display response contract
to an asynchronous native reader interface. It does not replace the accepted
build 4000027 engine, image payload or iPhone results. The separate build 4000028
application compiles; package publication and actual phone acceptance are tracked
in STATUS.md. Compiler results do not establish the native completion join.

## Implemented source

ABI2 configuration is exclusive with the existing ABI1 callback. INSTALL and
DISABLE carry metadata only. Each FLUSH reader has a session, command, reader,
resource and installation-generation token. The host must immediately retain
the borrowed texture/backing before returning acceptance. It must submit no GPU
read if it rejects the event. Only actual GPU Completed/Error can return a
ticket; CPU deadlines and display presentation times cannot return ownership.
The separate cancel entry point fails a retained ticket only before any GPU
command reads its source. It is never reported as an actual GPU terminal.

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

1. Verify the compiled, integrated ABI2 consumer on the phone. It retains texture/backing through
   actual Metal terminal callbacks, reports command errors and submits on a
   separate executor. The main thread prepares only the stable native surface.
   Source-reader completion and actual presentation timestamps remain separate.
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

The generic host consumer has an explicit 16-reader / 128 MiB retained-backing
budget (32 MiB per backing), a stable pure-Metal surface and asynchronous Metal
completion callbacks. It counts cancellation before submission separately from
real GPU errors. No device GPU terminal or display timing is inferred from an
enqueue, CPU timeout or cancellation. Source events may have gaps when the
engine rejects an unowned refresh; accepted event sequence numbers must increase.

The separate standard-KMS producer is derived from the exact pinned Vulkan
diagnostic sources without changing them. It retains the real Vulkan producer
fence wait and external queue release, then uses TEST_ONLY, a blocking atomic
modeset and seven nonblocking atomic flips with actual output sync-file checks.
The old legacy SetCrtc/DirtyFB and fixed dwell are removed from that variant.
No custom UART release is used. A missing terminal/event or invalid ownership
query leaves the guest paused with its images/GEM resources retained. Successful
cleanup requires all eight prior frame dependencies to be positive before
disabling the output. Its hosted missing-3D/device/software controls cannot
establish a positive native path; that still requires the actual iPhone.

The new `NativeKMS.xcodeproj` links only the fresh native KMS runner/surface/
receipt and shared fresh JIT, diagnostics, observer and ABI2 consumer. It does not
link the old UART moving transport, old VM app, Madeira app or old native preview.
It has a separate bundle identifier, preserves the previous diagnostic app and
uses one engine initialization per process. The generic consumer records bounded
actual terminal identities. The receipt matches them by exact resource, rather
than depending on callback bookkeeping order, and requires callback bookkeeping
itself to have finished before accepting shutdown. Shared fresh recovery journals
and StikDebug routing remain available. No logs are uploaded automatically.

## First packaged native KMS prerelease

[Build 4000028 / native-kms-2](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-native-kms-2)
was built from source `3a7932c57030900ab6201b72e1acf4587df92b0c` in
[run 37343003113](https://github.com/aghjkshdsj/My-pc/actions/runs/37343003113).
The complete IPA was independently downloaded on this PC; ZIP CRC, physical-iOS
Mach-O type/platform, ten-framework dependency closure/code identities, the new
engine binary, exact kernel/initramfs and build/source identity all pass.
IPA size 23,786,127 bytes; SHA-256
`a193909a99064b7a2469a7935809ccffab0107b16a2c71c95c4a0f19b9469f35`.
The hosted package audit also matched dSYM UUID
`64E20628-E01D-3AC4-B38D-47CD239BB719`. The source closure and original notices
are published with a complete hashed source/package index. Local IPA verification
does not establish local source-archive bytes, a live GPU completion or phone success.

The fresh app installs under a separate bundle identifier as My-pc Linux Display.
Enable StikDebug universal.js, pass ARM64 JIT, then open/start the Linux standard
display test once in a fresh process. Keep foreground without rotation for up to
three minutes; share the device report and saved logs. On interruption, reopen
and share recovery logs. An accepted phone result requires eight joined resources,
eight positive output fences, seven correct events, actual Metal terminals,
zero outstanding readers/callback bookkeeping/backing/images, and exact same-worker
engine cleanup/RCU retirement/join. Desktop, ARM Steam and game FPS remain unverified.
