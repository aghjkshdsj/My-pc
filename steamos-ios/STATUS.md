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
- The latest actual Linux attempt passed its native JIT precheck and payload
  hashes, loaded QEMU and found required exports. Initialization failed:
  `allocate 1003421696 bytes for jit buffer: Operation not permitted`.
  The kernel serial log was empty. **Linux has not booted on the phone.**
- Recovery exports preserved pending markers, native stages and engine output.
  Actual presentation of the reopen sharing popup has not been directly observed
  by the developer.

## Prepared fix and required retest

Build 4000007 requests `tcg,thread=multi,split-wx=on,tb-size=32`.
The pinned release engine defaults split-WX off, selecting MAP_JIT on Darwin.
Its default cache uses up to one eighth of physical RAM, matching the roughly
957 MiB allocation denied on the phone. Forced split-WX selects the Darwin
RX/writable-alias path; the requested cache is 32 MiB. Its legacy region callback
is configured separately through the universal debugger protocol while attached.

Repeated native JIT checks execute one retained successfully prepared host-page
region again; cached receipts never count as new execution. The UI shows the
last durably saved stage and a readable result. **The fix needs new phone
evidence and is not a verified successful boot.**

Primary sources: [allocator](https://github.com/utmapp/qemu/blob/v10.0.12-utm/tcg/region.c),
[TCG defaults](https://github.com/utmapp/qemu/blob/v10.0.12-utm/accel/tcg/tcg-all.c).

Latest independently verified public IPA before this fix:
[Linux-gate-5 / build 4000006](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-linux-gate-5),
source `dac0d7d6d4f8c10100e986cf67e9adc3668e792b`, 8,069,591 bytes, SHA-256
`adc3e7abd2afc736bd424ed66bd6a32cdcdbd9f6921deefc5dc56225055d100a`.
[Build 37024755837](https://github.com/aghjkshdsj/My-pc/actions/runs/37024755837)
passed actual ARM64 iOS compilation and hosted abrupt-exit recovery tests.
Independent ZIP CRC, physical-iOS Mach-O, dependency closure, payload hashes
and compiled universal ABI wrappers passed.

The disposable Linux gate uses Linux 6.12.111 / BusyBox 1.38.0, 2 vCPUs,
512 MiB RAM, no persistent disk/network/GPU. It checks signals, mmap/protection,
pthread/TLS/futex, fork/exec, checksum and a fresh serial nonce. QEMU TCG is
**software system emulation**, not public iOS hardware virtualization. FEX later
adds x86-to-guest-ARM compatibility inside Linux. This gate is not a substitute
for the requested SteamOS product.

## Build and graphics evidence

| Result | Evidence | Remaining limit |
|---|---|---|
| Source-built ARM64 iOS QEMU engine/dependencies | [37014232362](https://github.com/aghjkshdsj/My-pc/actions/runs/37014232362) | Phone loader passed; kernel execution failed at allocation |
| Source-built Linux/BusyBox ABI gate | [37014232445](https://github.com/aghjkshdsj/My-pc/actions/runs/37014232445) | Hosted TCG boot passed; not phone boot |
| Hosted GL/Vulkan diagnostics | [37035517982](https://github.com/aghjkshdsj/My-pc/actions/runs/37035517982) | Software rendering only; explicitly rejected as acceleration |
| Native iOS MoltenVK compile/package | [37036404372](https://github.com/aghjkshdsj/My-pc/actions/runs/37036404372) | Not in IPA or executed on phone; loader/import behavior needs checking |
| Hosted Venus serialization attempt | [37037502542](https://github.com/aghjkshdsj/My-pc/actions/runs/37037502542) | Renderer compiled after C11 label fix; client aborted; transport unverified |

Vulkan rendered two 1280×720 images, checked all 1,843,200 pixels, channel sum
1,219,256,320 and synchronization validation. Zero mismatches/errors passed
on Mesa llvmpipe/lavapipe; software-as-acceleration was rejected with exit 20.
Receipt: `evidence/primary/hosted-vulkan-diagnostic.json`. No swapchain,
presentation, guest transport or game performance is implied.

MoltenVK revision `05604465d691118cfd20f53a48ecf1aad9c12f93` and seven pinned
dependencies produced a physical-iOS ARM64 library and corresponding source.
Receipt: `evidence/primary/hosted-moltenvk-build.json`. Its IOKit load command
needs classification and phone loading evidence before integration.
The latest GL classification rerun failed its second Xvfb startup; isolated
automatic display selection is prepared. Venus failure output will expose
renderer/client/validation logs. Neither failure was waived.

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

Next: pass the physical Linux gate; prove real guest GL and Vulkan transport
to Metal and moving presentation; integrate authenticated SteamOS, actual ARM
Steam/CEF, Game Mode/desktop and FEX/Proton through the coverage ledger.
Native host/Metal optimization does not remove guest TCG translation costs.
**Steam usable under 60 seconds and Hollow Knight 60–80 base rendered FPS at
1280×720, including sustained thermal/frame-pacing measurements, are unverified.**
