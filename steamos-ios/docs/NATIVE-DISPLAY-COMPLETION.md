## Phone evidence and optional API validation correction, 2026-10-05

Both supplied build-4000028 reports pass the independent eight-image raw
completion/ownership audit. Each has eight actual native reader completions,
eight positive standard Linux output fences, seven matching flip events, zero
pending readers/callbacks/backings/images and a completed same-worker engine
retirement/join. Their original app verdicts remain failed; the recovery export
contains an identical completed result and no pending-test marker.

The older receipt mistakenly required `VK_LAYER_KHRONOS_validation` despite
this payload's optional-validation producer not bundling that layer. The new
receipt accepts explicitly typed, consistent availability flags (both enabled
or both unavailable), while still requiring zero reported validation errors and
all the same actual pixel/fence/reader/teardown checks. Missing metadata,
inconsistent flags, numeric/string boolean substitutes, an invalid error count,
and actual ownership failures are rejected. Unavailable layers never become
verified API validation. Build 4000029 also displays this limitation.

The private independent checker requires explicit `--observations-only` for
older failed app verdicts; it preserves original status/verification fields and
rechecks actual engine/payload/device identity, complete raw serial rows and
actual guest Metal samples. This option bypasses only derived app labels.
It does not bypass missing completions, errors, stale identities or cleanup.
Both originals pass; 36 altered real-report copies fail. Private source reports
and audit files are excluded from public uploads. This is a bounded device
observation audit, not signed hardware attestation or a performance benchmark.

Ordinary compositor/WSI, mutable buffers, client release synchronization,
interrupt/reset/cursor lifetime stress, display timing, desktop/Steam/games and
performance targets remain open. Historical build notes below retain their
original pending-device statements as history.

---

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


The final [native-kms-3](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-native-kms-3)
package uses the same compiled application code with source identity
`bff919948ae41240b4e479bf7f826675149c2b3e` and two additional duplicate-token/
generation rejections. All 33 native optimized/sanitized controls pass, including
valid callback-bookkeeping reordering. IPA SHA-256
`5726cd7eff45c357a44dec36b5b615d6cb2e6e82192ea47ce3e7860df95cbaf0`,
23,786,127 bytes. The complete IPA, fresh source and matching crash dSYM were
independently downloaded and verified on this PC. Compiled source inputs match
the published source archive. Upstream source archive bytes remain independently
unverified locally; their complete published files and pinned hosted audits are
separate evidence. Details: `evidence/primary/native-kms-prerelease-3.json`.

`tools/verify_native_kms_report.py` independently checks the private new report
against the exact expected IPA source, the owner's model/OS, raw Linux producer/
flip/pixel/cleanup rows, unique matching actual Metal reader terminals, actual
guest Metal observer identity/timing, zero outstanding ownership and same-worker
engine retirement/join. It requires the reported target iPhone16,2 / iOS27.0.1 /
24A446. Tests use labeled synthetic fixtures only, including 32 ownership mutations
plus source/device/retirement/observer/type controls. No device verdict is inferred
from those fixtures or the app's declared pass. No private report is uploaded.
