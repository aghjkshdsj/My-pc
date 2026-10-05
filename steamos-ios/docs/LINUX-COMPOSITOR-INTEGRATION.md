# Ordinary Linux display integration

The next component uses standard Linux DRM/KMS and Linux compositor APIs in the
existing fresh ARM Linux/QEMU/Venus/virgl/MoltenVK/Metal architecture. The moving
producer's UART acknowledgements are specific to that diagnostic and cannot be
required from unmodified KWin, gamescope, Mesa WSI or Steam. This work does not
replace the requested SteamOS desktop/Game Mode with a host-drawn desktop.
Owner phone results remain in the ignored local device record.

## Implemented first control

`Guest/kms_atomic_gate.c` selects a real connected 1280x720 output and compatible
primary XRGB8888 plane by querying DRM objects and properties. It allocates
three CPU dumb buffers, validates a complete atomic request with TEST_ONLY,
rejects invalid geometry and an invalid input-fence descriptor when that
property exists, performs a real blocking modeset, and submits six nonblocking
atomic flips. It checks the exact CRTC event and, if exposed, an actual output
sync-file's positive terminal status for each flip. It disables the output,
unmaps/removes buffers and drops master before closing its descriptor.

The new build workflow compiles the actual AArch64 program and boots it with
the previously pinned Linux 6.12.111 image and userspace. It also boots with the
display device removed. The accepted phone IPA, guest image, old projects and
user data are unchanged. The extra binary and init change live in a separate
disposable control payload. Complete parent corresponding source and new source
are packaged together; libdrm header/license notices are retained. Dynamic
linking uses the parent's libdrm/libc, and successful execution must verify
that dependency closure instead of silently adding a second Linux ABI stack.

This control is deliberately CPU-rendered under hosted QEMU TCG software system
emulation. Neither KMS property presence, a virtual page-flip event, a signaled
DRM output fence nor successful TEST_ONLY establishes actual native Metal
reader retirement. All native GPU, display, compositor, desktop, phone and game
acceptance fields remain false. Synthetic altered-receipt tests are separate
from actual kernel boots. Actual ARM compilation and two Linux boots pass in run 37264039773 at source
62df335c7f13401bd117d09b0b3f869bef43e863. Six nonblocking flips and six positive
output sync-files complete; invalid geometry returns ERANGE (34) and an invalid
input-fence descriptor returns EINVAL (22). Removing the device rejects at open
with ENOENT (2). Both fence properties are present. All event sequence numbers
are 0: virtual events cannot establish physical display timing. Nine source
receipt tests and 134 combined Python tests pass; nine independent changes to
the actual logged result reject. See
`evidence/primary/hosted-kms-atomic-api-control.json`.

The audit independently checks the successful job and emitted boot receipts.
The connector returned both artifact references, but local download requests
returned HTTP 403. Independent ZIP/payload/corresponding-source byte inspection
is still pending and is explicitly false; published archive digests are
reported build values. This does not change the verified build 27 IPA audit or
owner evidence, and does not certify production display fencing.

## Required production connection

The pinned source trace identifies an unfenced host3d primary-plane path and a
50 ms wait whose return value is ignored. The additional exact-source audit,
`evidence/primary/kms-native-completion-source-gaps.json`, also records the
renderer-only fence watermark and an OK response after renderer-context fence
creation fails. Those paths cannot certify native display retirement. Display
completion must join producer and native-reader results with exact identities
and propagate errors; ordinary renderer progress cannot release a live reader.
These are source integration gaps, not evidence of an iOS platform blocker.
The current callback ABI is borrowed
and lacks an explicit terminal result. Enabling a standard property or adding a
timer cannot repair that dependency. The next adapter must establish all of:

1. Real producer completion for each imported image before the native reader.
2. A bounded native reader lease bound to exact resource/incarnation/content.
3. Actual successful Metal terminal completion handed to the owning engine
   executor before the matching guest-visible completion can signal.
4. An error/cancel path which quarantines a live reader instead of authorizing
   buffer reuse through an enqueue, fake vblank or elapsed deadline.
5. Standard KMS/WSI recycling without diagnostic UART messages from applications.
6. A delayed native-reader test that keeps the guest dependency unsignaled,
   plus missing/failed-reader, resize, removal and shutdown controls.

Atomic completion is also distinct from actual iPhone display timing. Missing
drawable timestamps remain incomplete even when every GPU reader has retired.
The current synchronous diagnostic consumer must not become an unbounded
production engine/main-thread wait. A production queue must retain sources,
handoff completion safely and drain on interruption without double release.

## Real compositor and SteamOS session acceptance

An isolated opt-in Linux 6.12.111 source fork now joins primary plane updates to
their exact fenced RESOURCE_FLUSH response. It obtains producer dependencies
with the standard GEM atomic helper, retains their eventual error status,
allocates an independent Linux fence context for each primary display response,
waits without the old 50 ms timeout release, and carries an erroneous response
into the transaction's OUT_FENCE before its virtual event is sent. OOM and
reservation-lock failures also mark that transaction as failed. Primary display
work uses the transaction's retained new state, so a subsequent nonblocking
state swap cannot change the buffer/fence being awaited. This fork compiles
and passes the four actual hosted controls below; it is not native Metal proof.

The separate hosted workflow compiles this kernel and a CPU-only QEMU fault
control, then boots real delayed, error, failed-producer and missing-response cases. The guest
requires its OUT_FENCE and event to remain pending beyond 50 ms; an injected
error must produce a negative sync-file status, and an absent response must keep
objects retained. That last disposable VM is deliberately killed by the test
host after recording retention; it does not claim graceful cleanup. The injected
QEMU timer only schedules a test response and is never a production buffer
release deadline. Importing an actual failed sync-file through IN_FENCE_FD
produces a failed output fence without issuing a third display flush. Neither
control engine nor this fork is installed in an IPA.

Verified hosted run: [37327189927](https://github.com/aghjkshdsj/My-pc/actions/runs/37327189927),
compiled source a3455de052b85b994de9341d6d74081ea31dd6b0. The kernel's normal
mapped-resource and missing-device controls also pass; the unchanged image
payload/rejection pipeline passes in run37327189955. All 141 Python tests pass.
The independent actual job/boot-log audit accepts the four distinct sessions
and rejects 29 altered real-result controls. See
`evidence/primary/hosted-linux-display-completion-control.json`.

Published artifacts retain the full parent userspace source, modified kernel
source/patch/build inputs and CPU test-engine source/patch/build inputs. Their
reported hashes and GitHub metadata are recorded. The combined 686,814,009-byte
control artifact exceeds the connector's 536,870,912-byte download limit;
independent local artifact-byte/source-package verification remains pending.
Job-log validation and local reconstruction of six pinned patched source files
are separately recorded and do not imply an independent binary-package audit.

The production engine still must defer its exact display command until every
matching native reader is terminal, including failure and disable/unregister
drain. Its renderer watermark must not release a command still read by Metal.
Cursor completion and disable completion also require their own joins before
full compositor lifetime safety can be accepted. Ordinary producer-fence,
native-reader, interruption and repeated buffer reuse acceptance remain open.

Only after that dependency is wired should a real compositor produce changing
buffers with standard APIs and accept pointer/key/controller input. A small
upstream compositor may be used as an explicitly identified Linux integration
control; that is not the SteamOS Plasma desktop or gamescope Game Mode. The
requested sessions still require their actual upstream engines and coherent
Valve ARM rootfs/Qt/Wayland/graphics/runtime dependencies.

The official rootfs metadata probe has not reconstructed/authenticated or booted
the full SteamOS image. Valve ARM Steam/CEF installation, networking/downloads,
writable storage, FEX/Proton and game launch remain separate component rows.
Do not mix arbitrary build-runner libraries into the official runtime, publish
proprietary client/rootfs binaries as new public artifacts, or infer licensing
permission from an accessible download URL. Necessary QEMU/Linux/Mesa/Wayland/
compositor reuse retains each upstream notice and applicable corresponding-source
requirements; original host adapter code does not change those obligations.

Primary references checked 2026-10-05: Linux's
[explicit fencing properties](https://docs.kernel.org/gpu/drm-kms.html#explicit-fencing-properties)
define input producer and output display fences; its
[dma-buf synchronization](https://docs.kernel.org/driver-api/dma-buf.html)
describes reservation/explicit dependencies. Upstream
[Weston backend/renderer documentation](https://wayland.pages.freedesktop.org/weston/toc/running-weston.html)
separates DRM, nested backends and renderer choices. These sources describe the
interfaces; they do not certify this iOS bridge or license a desktop substitution.

Steam usable under 60 s, Hollow Knight 60–80 base rendered FPS at 1280x720,
production frame pacing, bounded memory, fast downloads and sustained thermals
remain unverified until actual product workloads are measured on the phone.
