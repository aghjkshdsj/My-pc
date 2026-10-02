# Verified state and next work — 2026-10-02

The complete SteamOS ARM/FEX product is **unfinished**. No architecture
substitution was approved or adopted. Previous projects, applications, disks,
credentials and game data are preserved. The fresh source and Xcode target use
no Madeira, old VM app or native-preview application implementation. Attached
documents and scripts were treated as reference material.

## Physical phone evidence

Owner-supplied reports identify iPhone 15 Pro Max (iPhone16,2), iOS 27.0.1
build 24A446 and 16 KiB host pages. iLoader and StikDebug 3.1.10/universal.js
are owner-confirmed. Raw reports remain private and outside the public allowlist.

- Earlier native CPU, Metal compute/readback and temporary storage correctness
  passed. These are not guest graphics or game measurements.
- Three build 4000006 native ARM64 JIT checks executed the generated local stub
  and returned 42. Source/device/scope consistency was checked against the exact
  independently verified IPA. This is not cryptographic remote attestation.
- One repeated JIT preparation was interrupted before universal RX preparation
  returned. Its cause beyond that stage is not established.
- The build 4000006 Linux attempt passed its native JIT precheck and payload
  hashes, loaded QEMU and found required exports. Initialization failed:
  `allocate 1003421696 bytes for jit buffer: Operation not permitted`.
  The kernel serial log was empty. This failure is preserved as historical evidence.
- **Build 4000007 booted Linux 6.12.111 on the actual phone.** Signals,
  mmap/protection, pthread/TLS/futex, fork/exec and checksum passed with zero
  failures and engine exit 0. The embedded and separately saved serial/receipt
  agree with the exact IPA/payload/source. Recorded kernel-plus-ABI time:
  691.06 ms. This is one disposable-kernel run, not SteamOS startup or game FPS.
  Fresh and retained-region native JIT checks also returned 42.
- Recovery exports preserved pending markers, native stages and engine output.
  Actual presentation of the reopen sharing popup has not been directly observed
  by the developer.

## Verified CPU fix and next native graphics gate

Build 4000007 requests `tcg,thread=multi,split-wx=on,tb-size=32`.
The pinned release engine defaults split-WX off, selecting MAP_JIT on Darwin.
Its default cache uses up to one eighth of physical RAM, matching the roughly
957 MiB allocation denied on the phone. Forced split-WX selects the Darwin
RX/writable-alias path; the requested cache is 32 MiB. Its legacy region callback
is configured separately through the universal debugger protocol while attached.

Repeated native JIT checks execute one retained successfully prepared host-page
region again; cached receipts never count as new execution. The UI shows the
last durably saved stage and a readable result. The owner-supplied build 4000007
logs passed the physical Linux evidence checker. Raw device evidence remains private.
Build 4000010 packages a native offscreen Vulkan-to-Metal shader check. Its
actual ARM64 iOS compile, recovery tests, 31 evidence tests and independent public
IPA checks passed. The owner-supplied build 4000010 report now passes the physical
native Vulkan-to-Metal offscreen evidence check on iPhone16,2 / iOS 27.0.1.
The Apple A17 Pro GPU rendered both 1280×720 images: 1,843,200 checked pixels,
zero mismatches and channel sum 1,219,256,320. Engine/shader/source identity
matched the exact IPA. Native setup/draw/readback/teardown took 497.20 ms.
Khronos/synchronization validation was not enabled on the phone; zero reported
validation errors is not a validation-layer pass. No cryptographic device
attestation, Linux graphics, presentation, Steam or gameplay completion is implied.
The supplied build 4000008 phone report failed the whole-file MoltenVK hash check
at `payload-sha256`, before loading the renderer. It does not show a render failure.
The supplied build 4000009 report passed executable-code identity, loaded MoltenVK
and returned from the native draw with exit 0 in 562.53 ms, without StikDebug.
Its parsed diagnostic object was empty, so GPU identity/pixel/checksum acceptance
remains false. This is not accepted as an offscreen graphics pass. The exact
mixed-output capture/parsing failure cause is unproven without the saved output.
Build 4000010 saves a separate exclusive-create, flushed/fsynced JSON receipt,
bounded engine output in reports and receipt-preserving recovery sharing. All
hardware/pixel checks remain enforced. Actual ARM64 iOS compilation, hosted
recovery/export tests, 31 evidence tests and independent public IPA verification
passed. The real hosted Vulkan adapter regression passed five cases: missing and
corrupt shaders, complete draw receipt despite invalid UTF-8 stdout, preserved
existing receipt and missing destination directory. These are software hosted
Vulkan tests, not phone Metal proof. The separate owner-supplied phone result
is recorded above; its raw JSON and signing identifiers remain private.
The source-pinned native iOS Venus renderer compiled successfully in
[run 37064765557](https://github.com/aghjkshdsj/My-pc/actions/runs/37064765557),
source `e8a730eb608c56fac7f03456444b83f07a6f4414`. Both ARM64 physical-iOS
frameworks passed platform/dependency and eight required renderer-export checks.
The renderer uses same-process threads and an explicit MoltenVK framework loader
adapter. The first run stopped at missing host PyYAML; pinned PyYAML 6.0.3 resolved
that code-generation dependency. Exact source, patch, cross recipe/config and
license-containing source archives accompany the binary artifact. This is compile
evidence only: no phone Venus load, host-memory import, guest transport or
presentation result is implied. Receipt: `evidence/primary/hosted-ios-venus-build.json`.

Primary sources: [allocator](https://github.com/utmapp/qemu/blob/v10.0.12-utm/tcg/region.c),
[TCG defaults](https://github.com/utmapp/qemu/blob/v10.0.12-utm/accel/tcg/tcg-all.c).

Phone-verified CPU baseline:
[Linux-gate-7 / build 4000007](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-linux-gate-7),
source `f18e3c3d91ba8bdf6b55c6e6cb7a33db4ea65841`, 8,075,687 bytes, SHA-256
`ec52d95d65e434911d21e77e218649d5da99786342afa9b7c7ebbda72b1e411c`.
[Build 37055171760](https://github.com/aghjkshdsj/My-pc/actions/runs/37055171760)
passed actual ARM64 iOS compilation and hosted abrupt-exit recovery tests.
Independent ZIP CRC, physical-iOS Mach-O, dependency closure, payload hashes
and compiled universal ABI wrappers passed. The compiled 32 MiB split-WX
argument was checked. Linux-gate-6 was misversioned by an old packaging override;
it is superseded by gate-7. Packaging now requires the intended build identity.

Latest independently verified graphics-bearing IPA:
[Linux-gate-10 / build 4000010](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-linux-gate-10),
source `208647c2f7c18f32fcf894771756c0fbeb487374`, 9,528,852 bytes, SHA-256
`3d11c3815b5108406019074787975d53426edb21fa085fc61643a378abf69dba`.
[Build 37062587594](https://github.com/aghjkshdsj/My-pc/actions/runs/37062587594)
passed actual ARM64 iOS compilation, recovery tests and 31 evidence checks.
Independent verification checked all five frameworks, exact engine/shader/kernel
hashes, source/build identity, compiled native adapter, universal ABI wrappers,
ZIP CRC and absence of IOKit/private-framework imports. MoltenVK is loaded inside
diagnostic capture rather than as a required app-startup dependency.

[Hosted adapter run 37062587136](https://github.com/aghjkshdsj/My-pc/actions/runs/37062587136)
passed real missing/corrupt shader errors without terminating the test process,
plus the real two-image draw through dynamically loaded Vulkan functions. Only
the hosted fixture permits its software driver; production source is unchanged
and rejects software. These tests do not count as physical Metal evidence.
The native phone check has passed; no repeat of build 4000010 is required.
The next phone gate must exercise guest graphics and the native memory/context
bridge after its implementation and independent IPA checks.

Build 4000009 corrects a signing compatibility issue in build 4000008's runtime
engine check: iLoader can change whole-file framework hashes while signing.
The new gate checks ARM64/physical-iOS identity and the engine's executable
__TEXT,__text section against original provenance. Offline unsigned IPA hashes
and complete shader hashes remain exact. Signing-metadata/code-tamper rejection
tests passed. The corrected public IPA was independently downloaded and verified;
its initial phone receipt was incomplete; build 4000010 later passed the native
offscreen gate. A simulated signing-metadata change
preserved the actual engine code identity while changing its full-file hash.
That simulation is not phone signing or rendering evidence. Build 4000008 is
superseded by build 4000009; no previous application or user data was deleted.

The disposable Linux gate uses Linux 6.12.111 / BusyBox 1.38.0, 2 vCPUs,
512 MiB RAM, no persistent disk/network/GPU. It checks signals, mmap/protection,
pthread/TLS/futex, fork/exec, checksum and a fresh serial nonce. QEMU TCG is
**software system emulation**, not public iOS hardware virtualization. FEX later
adds x86-to-guest-ARM compatibility inside Linux. This gate is not a substitute
for the requested SteamOS product.

## Build and graphics evidence

| Result | Evidence | Remaining limit |
|---|---|---|
| Source-built ARM64 iOS QEMU engine/dependencies | [37014232362](https://github.com/aghjkshdsj/My-pc/actions/runs/37014232362) | Phone loader and CPU gate passed after allocation configuration fix |
| Source-built Linux/BusyBox ABI gate | [37014232445](https://github.com/aghjkshdsj/My-pc/actions/runs/37014232445) | Hosted and build 4000007 phone boot passed; no SteamOS image yet |
| Hosted GL/Vulkan diagnostics | [37035517982](https://github.com/aghjkshdsj/My-pc/actions/runs/37035517982) | Software rendering only; explicitly rejected as acceleration |
| Corrected native iOS MoltenVK compile/package | [37056046870](https://github.com/aghjkshdsj/My-pc/actions/runs/37056046870) | Build 4000010 phone GPU/pixel gate passed; no Linux guest transport or presentation |
| Hosted Venus external-host SHM test | [37056046909](https://github.com/aghjkshdsj/My-pc/actions/runs/37056046909) | Real serialized draws passed under explicit test override; software Linux host, not phone Metal |

Vulkan rendered two 1280×720 images, checked all 1,843,200 pixels, channel sum
1,219,256,320 and synchronization validation. Zero mismatches/errors passed
on Mesa llvmpipe/lavapipe; software-as-acceleration was rejected with exit 20.
Receipt: `evidence/primary/hosted-vulkan-diagnostic.json`. No swapchain,
presentation, guest transport or game performance is implied.

MoltenVK revision `05604465d691118cfd20f53a48ecf1aad9c12f93` and seven pinned
dependencies produced a physical-iOS ARM64 library and corresponding source.
Receipt: `evidence/primary/hosted-moltenvk-build.json`. The first compiled engine
had a required macOS IOKit load command. The corrected source-built iOS target
omits that framework; its final imports contain no IOKit. Both engine variants
and the original failure remain documented. Phone loading and draw return 0 were
observed in build 4000009; build 4000010 subsequently passed the complete native
GPU/pixel gate, without demonstrating Linux graphics or presentation.
The GL classification rerun passed with isolated Xvfb display selection.
Venus-only server configuration resolved its excluded-EGL initialization failure.
The unmodified Linux-native fd route then failed resource export; the explicit
external-host-memory test policy exercises the existing POSIX SHM branch instead.
That real draw test passed 1,843,200 pixels, zero mismatches/validation errors and
software rejection exit 20. Receipt: `evidence/primary/hosted-venus-shm-diagnostic.json`.
No unmodified fd-path, Darwin bridge, virtio guest, Metal or presentation pass is implied.

## Complete inputs and component coverage

The full handoff, archive docs/core scripts and prior build/performance lessons
were reviewed. All 3,672 archive files have CRC, size, SHA-256 and a component
assignment. [Coverage](docs/COMPONENTS.md) accounts for all 19 groups plus
Game Mode, desktop/compositor, input, audio, storage/downloads, FEX/Proton,
overlays/plugins, lifecycle and external dependencies. Source presence does not
complete a product feature. [Performance](docs/PERFORMANCE.md) and
[licensing/provenance](docs/PROVENANCE.md) remain applicable.

Official stable ARM manifest 1788652215 resolves 35 package URLs totaling
1,008,581,976 bytes with expected HEAD sizes. Full download/hash/signature
authentication, installation and Steam execution remain open.
Official rootfs 20260921.6090922 / 0.5.0 resolves a 10,737,418,240-byte image,
88,387 chunk records and three hash-verified samples. Complete reconstruction,
image hash, RAUC CMS trust and generic-virt compatibility remain open.
No Valve/game/credential data has been redistributed.

Next: integrate the compiled native Venus renderer and prove real guest GL and Vulkan transport
to Metal and moving presentation; integrate authenticated SteamOS, actual ARM
Steam/CEF, Game Mode/desktop and FEX/Proton through the coverage ledger.
Native host/Metal optimization does not remove guest TCG translation costs.
**Steam usable under 60 seconds and Hollow Knight 60–80 base rendered FPS at
1280×720, including sustained thermal/frame-pacing measurements, are unverified.**


## Current guest graphics implementation

A fresh graphics-capable Linux 6.12.111 kernel now includes generic PCI, virtio
PCI/MMIO and DRM virtio-GPU. It is kept separate from the phone-verified CPU
kernel and uses the same source-pinned Linux/BusyBox archives. Hosted ARM TCG
[run 37067848259](https://github.com/aghjkshdsj/My-pc/actions/runs/37067848259),
source `6ab4df9f78ec307e026f378658673efa3ebeeec2`, passed real DRM driver/version
queries, 1280×720 resource allocation/map, CPU pattern verification, transfer
ioctl completion and resource cleanup. The same guest correctly failed at
`open-drm` with ENOENT when the GPU was removed, with fresh separate nonces. Both
boots retained all Linux ABI checks. Receipt: `evidence/primary/hosted-gpu-kernel-test.json`.
The first hosted attempt caught missing explicit BusyBox echo paths, after
the device operations succeeded; the corrected full run passed. This 2D test
does not establish host pixel contents, shaders, Venus, Metal or phone execution.
35 local evidence rejection tests and source isolation checks passed.

A new standalone ANGLE source recipe checks out only the pinned engine, common
configuration and ccache recipe paths. It uses the public iOS SDK, disables
private Metal ownership identity and retains original source/licenses plus every
patch. Actual Xcode builds exposed removed libc++ assertion settings, a constant
shift and intentional object-byte copies newly diagnosed by Clang. Targeted
hardening, `if constexpr` and reviewed explicit-copy repairs preserve assertions,
object bytes and hash padding. Guards check the reviewed value types; the
redundant-virtual style warning stays visible without becoming an error. All
other warnings-as-errors remain enabled. ANGLE compilation and ARM64 physical-iOS
platform/export/import audits passed in run 37075043878, source
`8fc4d429b8fd3158ddb9f9c0f2f51414e2e84f8f`. Neither framework requires IOKit,
Hypervisor or a private framework. Receipt: `evidence/primary/hosted-ios-angle-build.json`.
This is compile evidence only. A subsequent source inspection found that the EGL
shim dynamically opens its GLES implementation without an explicit framework
rpath. The fresh package uses an explicit `@rpath/GLESv2.framework/GLESv2` loader;
its generated implementation and generator are now patched together. The revised
engine passed run 37077105285, source `b925d37b18d0bb4d7721ea1aedc059b43f9240a1`,
including the same physical-iOS exports and import closure. Phone loading and
actual Metal context execution still require device evidence.

The separate QEMU GPU recipe, Darwin EGL/Metal root-context adapter and dependency
stager/source collector are implemented but not yet cross-compiled. The adapter
explicitly selects ANGLE Metal and GLES; its upstream headless readback is a
correctness diagnostic, not the planned steady-state presenter. The prepared
EGL-enabled virgl/Venus recipe will consume only an accepted ANGLE build. Its first
actual compile produced the EGL renderer object, but the final audit incorrectly
expected a numeric value for a Meson boolean macro. The audit now accepts only
the enabled bare-define or value-1 forms and checks the actual EGL compile command.
No accepted complete GL/Venus engine or phone loader result is claimed yet.

A new ARM Linux Mesa 26.2.2 recipe pins the official 68,533,264-byte archive to
SHA-256 `eeb29ca7e56cfaa8e8a79538dcf834e3b18e501c31bef5145e959ea437cc4216`.
Only virgl/Venus drivers are selected. Hosted run 37074804870, source
`9ddc641f25d83a230affb90c7e59174a041bde30`, passed actual ARM64 ELF library,
unified Gallium/compiled-virgl, ICD and shader compilation checks. The exact new
Venus ICD correctly failed physical-device enumeration with Vulkan -3/exit 3 in
a verified separate mount namespace with no DRM device nodes. Two earlier audit
failures caught an obsolete alias assumption and the host DRM-directory precondition;
both are retained. Receipt: `evidence/primary/hosted-guest-mesa-build.json`.
This is guest userspace, not a complete initramfs or SteamOS image. The full Mesa
source and exact recipe/settings are retained. External Linux loader/libraries
and their package/source versions are recorded separately; staging-directory
library lookup and source/license closure remain guest-payload work. No guest
shader or phone graphics result is implied by this compile/negative test.

Phone host-memory import, guest Mesa/Venus shader draws and moving Metal
presentation remain unfinished. The latest phone IPA is still build 4000010;
no new phone test is requested yet.
