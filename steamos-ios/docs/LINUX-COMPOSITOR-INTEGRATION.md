# Ordinary Linux display integration

The next component uses standard Linux DRM/KMS and Linux compositor APIs in the
existing fresh ARM Linux/QEMU/Venus/virgl/MoltenVK/Metal architecture. The moving
producer's UART acknowledgements are specific to that diagnostic and cannot be
required from unmodified KWin, gamescope, Mesa WSI or Steam. This work does not
replace the requested SteamOS desktop/Game Mode with a host-drawn desktop.
Owner phone results remain in the ignored local device record.

## Implemented first control

`Guest/kms_atomic_gate.c` selects a real connected1280x720 output and compatible
primary XRGB8888 plane by querying DRM objects and properties. It allocates
three CPU dumb buffers, validates a complete atomic request with TEST_ONLY,
rejects invalid geometry and an invalid input-fence descriptor when that
property exists, performs a real blocking modeset, and submits six nonblocking
atomic flips. It checks the exact CRTC event and, if exposed, an actual output
sync-file's positive terminal status for each flip. It disables the output,
unmaps/removes buffers and drops master before closing its descriptor.

The new build workflow compiles the actual AArch64 program and boots it with
the previously pinned Linux6.12.111 image and userspace. It also boots with the
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
from actual kernel boots. Build/boot acceptance is pending until its run and
downloaded artifacts have been independently checked.

## Required production connection

The pinned source trace identifies an unfenced host3d primary-plane path and a
50ms wait whose return value is ignored. The current callback ABI is borrowed
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

Primary references checked2026-10-05: Linux's
[explicit fencing properties](https://docs.kernel.org/gpu/drm-kms.html#explicit-fencing-properties)
define input producer and output display fences; its
[dma-buf synchronization](https://docs.kernel.org/driver-api/dma-buf.html)
describes reservation/explicit dependencies. Upstream
[Weston backend/renderer documentation](https://wayland.pages.freedesktop.org/weston/toc/running-weston.html)
separates DRM, nested backends and renderer choices. These sources describe the
interfaces; they do not certify this iOS bridge or license a desktop substitution.

Steam usable under60s, Hollow Knight60–80 base rendered FPS at1280x720,
production frame pacing, bounded memory, fast downloads and sustained thermals
remain unverified until actual product workloads are measured on the phone.
