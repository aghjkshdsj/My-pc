# Verified state and next work - 2026-10-04

**[Build4000026 / 120 changing Linux frames](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-22)**
passed device-target ARM64 iOS Release run37251790340 at compiled source
b62ad0a5ee279b283d0986cb9a64b6d171516333. The final public IPA and thirteen
other public assets were independently downloaded and hashed. The unchanged
engine corresponding-source archive was rehashed from its prior independent
download. All fourteen published checksum entries passed. The exact host dSYM
matches UUID 8433DD91-2AA4-326E-B06C-83A131B01E4C. IPA: 24,510,062 bytes,
SHA256: 14b6bb8afe85e4fcf41d58544173c8288b445326ba748a9e7e18cba1ba68f4fd.

All 46 selected source files match the published fresh-source archive after
explicit UTF-8 CRLF normalization. The new complete guest source archive was
independently checked against all 16 moving-source hashes, the exact retained
parent archive, required compile headers/copyrights and the packaged init
script. All 107 initramfs records were checked; only init changed and the ARM64
vk-moving-gate was added. All ten native frameworks, the graphics kernel and
the prior CPU payload remain byte-identical to build25.

The new phone test renders 120 changing phases at 1280x720 across three reused
buffers. Native Metal terminal completion authorizes each explicit diagnostic
UART release. Linux waits for a separate actual Vulkan external ownership
reacquisition fence before writing again. The final three acquisitions drain
the pool before shutdown. Readback is restricted to first/last images. Source
buffer reuse and positive display timestamps have separate verdicts; drawable
IDs may be zero or recycled, and missing display time cannot pass timing.

| Check | Verified scope | Still pending |
| --- | --- | --- |
| Hosted ARM Linux UART | Seven actual kernel boots accept valid/fragmented replies and reject wrong session/resource, corrupt, partial and missing replies | Actual iOS moving release path |
| ARM moving payload | AArch64 binary and dependency closure; two missing-3D boot controls and software Vulkan rejection | 120 actual GPU frames/reuses on the phone |
| Native ownership/recovery | 123 Python tests; 57 moving receipt rejection checks and 1,100,086 ownership checks per optimized/sanitized execution; 100,000 synthetic content reuses | Actual source-reader and display receipts |
| iOS package | Physical-device target compilation, exact bundle/source closure, independently downloaded IPA and matching host symbols | Owner execution of build26 |

Install the linked build26 and choose **Show changing Linux frames** then
**Start moving-frame test** as the first Linux test after a fresh launch, JIT
enablement and a passing ARM64 JIT check. Keep foreground without rotating
until finished and share the report/saved logs. Phone acceptance is pending.
See [build26 gate](docs/GPU-GATE-4000026.md) and the package-only audit
evidence/primary/ios-moving-output-prerelease-4000026.json.

Production KMS/Wayland/WSI fencing and compositor integration remain unfinished;
this explicit UART is a diagnostic handoff. SteamOS desktop/Game Mode, Valve
ARM Steam/CEF, FEX/Proton, controllers/audio/storage/downloads/overlays/plugins
and every startup/game/sustained-performance target remain open. QEMU TCG is
software system emulation, not hardware virtualization. This package grants
no measured performance result or new device acceptance percentage. Previous
entries below are historical checkpoints; private owner evidence stays local.

**[Build4000025 / initialization-thread retirement](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-20)**
passed ARM64 iOS device-target Release run37245060441 at source
928b1db91b1ee1713e70ddee2c5253ba6676ca93, plus rebuilt engine run37244178261.
Native thread/TLS tests passed 1,001 retirements in each optimized and
address/undefined-behavior-sanitized execution; these are lease-contract tests,
not execution of QEMU/iOS. All 115 Python and preserved native recovery/graphics
checks passed. Eleven public files were independently downloaded and checked,
including the new complete engine corresponding-source archive and actual
retirement export. All eighteen selected source files match the source archive.
IPA: 24,444,751 bytes, SHA256
1242db7d93eead6a9f3c00b268979b7db24e7c2b20586490a18468297ebae6ed.
Host dSYM UUID: D7C40BC0-BB7F-331B-AF02-CCD7118B1D92.
Only QEMU changed among the ten native framework binaries; nine frameworks
and the three guest payload/receipt files are byte-identical to build24. Three
unchanged corresponding-source archives have metadata/hosted checks this turn.

The host now unregisters qemu_init's RCU reader on that same worker after
cleanup, lock release and pool drain, before publishing completion and joining.
This corrects an identified registration-lifetime bug. Current device verdicts
are assessed in the private local coverage record; build/package evidence alone
cannot certify elimination of every delayed crash. This package adds no desktop,
game or performance milestone. Implementation now moves to changing Linux output
with explicit native reader release and guest reacquisition. See
[moving-output integration](docs/MOVING-OUTPUT-INTEGRATION.md); another unchanged
eight-frame repetition is not a prerequisite for that work.
See [thread retirement](docs/RCU-THREAD-RETIREMENT.md) and the package-only receipt
evidence/primary/ios-init-thread-retirement-prerelease-4000025.json.

**[Build4000024 / crash diagnostics](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-19)**
passed actual physical ARM64 iOS Release run37242218149 at source
bcfed4ecf78b86ebf415e1c02fdff44b56329363. Ten public files were independently
downloaded and checked. IPA: 24,442,389 bytes, SHA256
5e2438e776755d5c602f6f4072f09a2c8ee5101fc8c2bae665b39749ebb0f53c.
All nineteen selected source files match the released fresh-source archive;
the ten native frameworks and all four guest files are byte-identical to build23.
The host dSYM matches the actual packaged ARM64 UUID
8E04948B-5019-3578-B409-A7463CFE9AF3. It supplies host symbols, not upstream
framework dSYMs. Four unchanged corresponding-source archives have metadata/
hosted digest checks this turn; the unchanged guest archive also retains the
prior independent complete-source audit.

The Linux worker now retires its autorelease pool and is joined before receipt
finalization. Additional durable checkpoints locate interrupted finalization.
Apple MetricKit crash payloads, when delivered, are stored locally and included
in Share logs, without inventing an active nonce/build association or automatic
upload. Hosted recovery/identity/bounds/symlink rejection, 111 Python and the
original native receipt checks passed. OS delivery and crash correction on the
phone remain unverified. Graphics and the existing strict display checks stay
pinned. See [crash diagnostics](docs/GPU-GATE-4000024.md) and the package-only
receipt evidence/primary/ios-worker-crash-diagnostics-prerelease-4000024.json.

The next moving-output component, [mutable frame ownership](docs/MUTABLE-FRAME-TRANSPORT.md),
is implemented as a separate source contract. ARM run37242218154 passed both
optimized and address/undefined-behavior-sanitized executions, reusing three
resource IDs for 100,000 content frames and rejecting premature/stale release.
It is not yet connected to the native engine/guest release path and supplies
no phone animation, compositor or FPS proof. Owner device results are retained
in the local ignored coverage record. Full SteamOS desktop/Game Mode/ARM Steam,
FEX/Proton, audio/controllers/downloads/overlays/plugins and all startup/game/
sustained-performance targets remain unfinished. QEMU TCG is software system
emulation; no architecture substitution is adopted.


**[Build4000023 / eight Linux frames](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-17)**
passed physical ARM64 iOS Release run37234851404 at source
0e8e9ada1379790ae8c2b7bdea46cbc08ab7eaae. The public IPA was independently
downloaded and verified: 24,435,502 bytes, SHA256
d46041e816aecf069923d1d4cfd36c3ea3a55fe314c5c242ec386c9d96a4b1cf.
All 34 selected source files match the fresh-source archive. The kernel and ten
native frameworks are byte-identical to the verified build4000022 package.
The new guest corresponding-source archive was independently downloaded,
hashed and checked, including its exact parent archive, current compile headers,
copyright notices and all 13 frame source hashes. The three unchanged upstream
source archives have metadata/CI digest checks only this turn.

The new test receives eight distinct immutable Linux-rendered 720p images,
with eight native aliases and screen GPU completions. Only first/last source
images have full native correctness readbacks. GPU sequence acceptance and
actual display timing are separate; zero callback display timestamps still
leave timing unverified, and cannot establish FPS. The old two-image gate stays
strict. One consumer in flight and two drawables are allowed. Minimum guest
dwell is 125ms, not a measured frame-rate target or steady-state buffer protocol.

All 107 Python checks, 149 native frame receipt checks, 100 original screen
checks, existing image/guest/ledger/recovery/capture checks and the new resource
budget passed. This historical package checkpoint alone carries no device verdict; owner results are recorded privately. Full
SteamOS desktop, ARM Steam, FEX/Proton, compositor/WSI, input/audio/downloads,
overlays/plugins, startup targets, Hollow Knight FPS and sustained thermals
remain unfinished. QEMU TCG is software system emulation, not virtualization.
See [eight-frame gate](docs/GPU-GATE-4000023.md) and package-only receipt
evidence/primary/ios-eight-linux-frame-prerelease-4000023.json.

Earlier package checkpoints are retained below.

**[Build4000022 / Linux screen gate](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-13)**
passed physical ARM64 iOS Release run37230949031 at source
4ed0113618e9529a3744b32f1e4985a70919aa76. The published IPA was independently
downloaded and verified: 24,394,918 bytes, SHA-256
91631dd0556c8eb276b56818c2e8e4293e75da3eb7429801c515ef8587762253.
All 14 selected source files match the fresh-source archive; the exact kernel,
initramfs, guest/engine receipts and ten frameworks match verified build4000021.
All 98 Python, 100 native screen, 56 image, 28 guest and 27 ledger checks passed,
with recovery/capture and the production readback budget checks. Separate native
adapter run37230949056 and source boundary run37230949039 passed.

The presenter now commits GPU work, observes scheduling, then presents the real
imported Linux texture in a main-thread Core Animation transaction. It records
bounded interruption reasons and actual scheduling/enqueue/callback clocks.
A zero callback display timestamp remains failure; a later API query never
replaces it. The result UI explains preserved import/GPU work separately from
screen timing. This historical checkpoint records package evidence only; owner results are kept private. Continuous animation, pacing,
full SteamOS/Steam ARM and game targets remain unfinished. See
[transaction screen gate](docs/GPU-GATE-4000022.md) and the package-only receipt
in evidence/primary/ios-guest-screen-prerelease-4000022.json.

The older package checkpoints below are preserved historical results.

**[Build4000021 / Linux screen gate](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-12)** passed actual physical ARM64 iOS
Release build run37228324700 at source 391c73c46b09c793c5fad546989e7b833de2b431. The published 24,387,473-byte IPA
was independently downloaded and verified, SHA-256 bf9e9d53fe66e6bfcd374e882cb5c2ff32324aaf2cc8f969e6a564c6be42465f.
All 23 selected source files match the published fresh-source archive. The exact
Linux kernel/initramfs/receipt/bundle and all ten engine frameworks match the
verified build4000020 package byte for byte. All 92 Python checks, 75 native screen
receipt checks, preserved 28 guest / 27 completion / 56 image receipt checks and
recovery/capture passed. Separate physical-iOS adapter compilation run37228324724
and source boundary run37228324706 passed.

Show Linux-rendered images opens a real Metal screen for the two Linux phases.
Actual screen acceptance on the phone is pending. This is two changing test
images; continuous animation, pacing, full SteamOS/Steam and game performance
remain unfinished. Source/package evidence and actual device evidence remain
separate. See [screen gate](docs/GPU-GATE-4000021.md) and the package-only
receipt evidence/primary/ios-guest-screen-prerelease-4000021.json.


The complete SteamOS ARM/FEX product is **unfinished**. No architecture
substitution was approved or adopted. Previous projects, applications, disks,
credentials and game data are preserved. The fresh source and Xcode target use
no Madeira, old VM app or native-preview application implementation. Attached
documents and scripts were treated as reference material.

## Current source and build results

The owner-selected [DroidDeck blueprint](docs/DROIDDECK-BLUEPRINT.md) is mapped
across Linux/Steam, desktop, Proton/FEX, graphics/presentation, audio, input,
network/downloads, libraries/saves, overlays/plugins, apps, lifecycle and updates.
All 735 files are inventoried with CRC/hash/group coverage; two signing inputs
are counted with their names and digests withheld. Android's Linux-kernel/PRoot
and Adreno/AHardwareBuffer mechanisms are reference designs, not an adopted
Darwin compatibility layer or replacement Linux distribution.

**[Build 4000020 / guest image gate 11](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-11)**
passed run 37225278118 at source `85314b25222cf3fe14058ead85cc7869d9474e4b`.
Independently downloaded IPA: 24,352,061 bytes, SHA-256
`580244c2dd508fa0e8ba990c4d6035d1b1755530125229101cabc81ff872e0fd`.
Physical ARM64 iOS Release, 87 Python checks, 28 native guest checks, 27 ledger
checks, 56 image-receipt checks and recovery/capture passed. The actual production
readback budget was tested across two distinct resources, repeated callbacks and
14 invalid event/layout cases. Pixel-order fixtures still cover 1,843,200 synthetic
pixels. Native image adapter compilation passed separate run 37225278163.

A scanout reinstallation may retain the same immutable resource while changing
the display generation. The host now reserves one readback per distinct resource,
rejecting altered layout/format. Native and independent receipt validators retain
all generation/ownership ordering, require flush/disable for every installation,
and demand both distinct phase0/phase41 consumers at each resource's first flush.
Repeated first-image pixels cannot establish full import. The 4000019 duplicate
consumer failure has a strict private progress checker; original report status
is never rewritten into success.

Public IPA, fresh source, checksums and verification were independently checked.
Published and independent verification agree. All 15 changed source files match.
The exact kernel/initramfs/guest receipt/engine bundle and all ten framework
binaries match verified build 4000019 byte-for-byte. Guest source/run remain
453a1d1f19c04b5d49328f135db32257a22d8f30 / 37222125501; upstream engine and
completion observer sources, licenses and full corresponding sources are retained.

Build20 source/package evidence does not certify owner device results; current
owner import acceptance remains in the private device record. Visible presentation,
full SteamOS/Steam/CEF, FEX/Proton, product integrations and sustained game targets
need separate acceptance. Owner analysis stays local. See [current details](docs/GPU-GATE-4000020.md),
component coverage and `evidence/primary/ios-guest-image-prerelease-4000020.json`.

Preserved **[Build 4000019 / guest image gate 10](docs/GPU-GATE-4000019.md)**
passed run 37222312731 at ce223b3f79e876c0558e0ade50f8a79aa2933d18. It aligned
Vulkan BGRA8, DRM XRGB, virtio BGRX and Metal BGRA8, with real Linux framebuffer
format controls and independent package checks. Its sources/packages are preserved.

Preserved **[Build 4000018 / guest image gate 9](docs/GPU-GATE-4000018.md)**
passed compilation and independent package verification at source
`f095035b922c40f004db084b34c57834e9ca8266`, run 37218735620.
It corrected explicit modifier query/creation and memory-plane layout.

Preserved **[Build 4000017 / guest image gate 8](docs/GPU-GATE-4000017.md)**
passed physical iOS compilation and independent package verification at source
186c67b20b45b04a5b880bce01e392890e67872a, run 37216717671. It introduced the separate
native image import diagnostic. Its original package/source are retained.

Preserved **[Build 4000016 / guest Vulkan gate 7](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-7)**
passed run 37211515640 at source `ef4192e2798ccb9f909265b408ca73666792344a`.
Independent public IPA verification passed: 24,311,733 bytes, SHA-256
`9abbe6e13f4fa1a726c3e5bad9f8e4934d033ab3ca1b1d86a7ad9be73a47529b`.
Actual Release ARM64 iOS compilation, 63 Python evidence tests, 28 native guest
receipt checks, 27 production ledger checks and recovery/capture fixtures passed.
The real native Swift tests verify complete JSON receipts above the former limit,
bounded oversized JSON/plain logs, interruption/reopen and exclusions. Equal
positive start/end observations do not replace the two required timed buffers.
Engine and Linux payload identities are unchanged. Public fresh source matches
the shipped host/tests; published and independent IPA verification receipts agree.
The first new run failed to compile a throwing expression inside a Swift test
assertion. That fixture was corrected before the final successful run; no IPA
was published from the failed run. See [build details](docs/GPU-GATE-4000016.md)
and `evidence/primary/ios-guest-vulkan-prerelease-4000016.json`.

The [image-import/presentation review](docs/PRESENTATION-GATE.md) identifies
existing upstream Metal scanout handles, the implemented fresh import adapter and
the moving presenter still required. Compile evidence does not accept phone import
or presentation.
Actual device results and detailed coverage remain local in `evidence/device/`.

Preserved **[Build 4000015 / guest Vulkan gate 5](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-5)**
passed run 37204430462 at source `6aa8dc6a2be44c7941c1e89ad25e378d31485249`.
Independent public IPA verification passed: 24,311,595 bytes, SHA-256
`9e625eb1f51f6f8a20578fa0e8fc012b0bf0a939c6649515abdbc0409bbf8bda`.
Actual Release ARM64 iOS compilation, 62 Python evidence tests, 28 native guest
receipt checks, 25 production completion-ledger rejection checks and recovery/
capture tests passed. A separate source-built MoltenVK observer records actual
guest command-buffer completions and timing without extra GPU work; the old
QEMU/GL/Venus engine and corrected Linux payload remain exact. Public observer/
fresh source archives match the shipped engine and host. New integrated native
completion evidence is maintained separately in the local device record. Independent memory import,
moving output, full SteamOS and game targets remain unfinished. Device records
and detailed analysis remain local. See [build details](docs/GPU-GATE-4000015.md)
and `evidence/primary/ios-guest-vulkan-prerelease-4000015.json`.

Preserved **[build 4000014 / guest Vulkan gate 4](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-4)**
passed run 37177283208 at source `696f3b62d0064b8c33d6e34e14760cbc7558ceb6`.
The public IPA was independently downloaded and verified: 24,302,427 bytes,
SHA-256 `5f01aec63be5923d87b3eabf8e0a91c0e0e44853cb60a92e22b53281bfb20dd6`.
Actual Release ARM64 iOS compilation, 54 Python evidence tests, 28 native receipt
checks and production recovery/capture tests passed. The new app-private renderer
communication backing passed actual native Darwin tests and integrated engine
compilation. Ten native framework identities/imports, real adapter markers,
unchanged corrected guest payloads and ZIP CRC passed independent checks. The
public fresh/engine source archives match the package and contain the helper,
patch, native tests and original renderer source. This deliberately changes
communication allocation policy; existing mapping errors and all shader/product
acceptance checks remain. The public receipt is package-only; owner device
records and detailed matching analysis are retained locally. Independent Metal
completion/import, moving presentation, full SteamOS and performance targets
remain unfinished. See [build details](docs/GPU-GATE-4000014.md) and the build-only receipt
`evidence/primary/ios-guest-vulkan-prerelease-4000014.json`.

Preserved **[build 4000013 / guest Vulkan gate 3](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-3)**
passed run 37175158168 at source `8ae27c43baa43f5c193ede199725eacd2581b753`.
Actual Release ARM64 iOS compilation, 53 evidence tests, 28 native receipt
checks and recovery/capture/bounded-tail tests passed. Independent public
redownload verified 24,300,637 bytes and SHA-256
`b183d0ccf406d15bb9390bfa421178098f8686f0e00649c7d10a989ac397ecfe`,
ten framework code/import identities, corrected guest payloads, real diagnostic
markers and ZIP CRC. This build fixes the preliminary DRM render-target bind,
checks the renderer context result, logs real Venus allocation/blob failures
and attaches the host log tail to the normal device report. No allocator
fallback or success override was added. See [source/build details](docs/GPU-GATE-4000013.md).
This earlier package remains independently verifiable. It does not establish
guest rendering, full SteamOS, moving presentation or game performance.

## Physical phone evidence

Build 4000011's new guest Vulkan attempt **failed before Linux boot**. Its
private recovery export preserves successful JIT return 42 and all nine native
engine identities, then QEMU reports `Display 'egl-headless' is not available.`
The last stage is before qemu_init returns. The exact archived configuration
defines EGL/OpenGL but undefines CONFIG_PIXMAN, excluding the required headless
backend. Earlier compilation checks missed this dependency. The corrected engine
explicitly enables Pixman, audits the actual EGL-headless compile command and
exports a real backend-registration preflight. Replacement build 4000012 is
verified and published, described below. The corrected engine passed run 37092127907 at source
`544799c0646c272e253850f588a0a2dd52c2067f`: actual Pixman-enabled configuration,
EGL-headless object compilation and the exported registration function were
audited. The first corrected compile passed but its new symbol was omitted from
QEMU's explicit export list; that audit failure in run 37091066661 is preserved.
The final patch adds the export and declaration without relaxing the audit.
This is an engine packaging failure; no new Linux/GPU/Metal pass
or iOS graphics driver crash is inferred. Sanitized receipt:
`evidence/primary/ios-guest-vulkan-backend-failure.json`. Raw phone logs remain private.

Replacement **[build 4000012 / guest Vulkan gate 2](https://github.com/aghjkshdsj/My-pc/releases/download/steamos-ios-guest-gpu-gate-2/MyPCSteamOS-Guest-GPU-Gate.ipa)**
passed run 37092862752, source `aa2f8ccfb15eb53a96f70775be8e83ca0c5703b2`.
Actual Release ARM64 iOS compilation, 53 evidence tests, 28 production native
receipt checks and recovery/export tests passed. Independent public redownload
verified the exact 24,292,269-byte IPA, ten-framework import/code closure including
Pixman, backend registration export/preflight, guest payloads and ZIP CRC.
SHA-256: `256da95463a5594cc41b93f1f2a64a096418ce39ef7f2471af4ffb39c1dcdbf8`.
Receipt: `evidence/primary/ios-guest-vulkan-prerelease-4000012.json`.
The owner subsequently returned a fresh build 4000012 `linux_gpu` report.
Its exact source, payload, engine bundle and all ten executable code sections
match the independently verified IPA. Linux 6.12.111 booted, all ABI checks
passed, and the virtio-GPU kernel test allocated/mapped a 1280Ã—720 resource,
checked its CPU pattern with zero mismatches, completed the transfer ioctl and
closed it. 3D/blob/host-visible/context-init capabilities and Venus capset 4
were advertised. These facts do not prove host pixels or guest shaders.
Guest Vulkan failed at `vkCreateInstance` with result -1 and guest exit 3:
RESOURCE_CREATE_BLOB received ERR_UNSPEC, followed by invalid-resource errors
for map/unmap/unref. The engine completed normally with exit 0 and poweroff;
this report is a failed graphics test, not evidence of another app crash.
Kernel/ABI/DRM plus the failed Vulkan attempt took 1156.26 ms, not Steam startup
or game FPS. The normal report alone cannot distinguish the allocation/renderer/resource-
metadata failure branches. Build 4000013 adds precise native diagnostics and
includes the host engine output in the normal report. Subsequent raw reports
and matching recovery analysis remain local. Later source/build results are
described above; the current package is build 4000016.
Sanitized receipt: `evidence/primary/ios-guest-vulkan-4000012-partial.json`.
Raw reports and analysis remain private. Current per-device shader/completion
acceptance is recorded locally; independent image import, presentation, SteamOS
and game targets remain open.

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
The Apple A17 Pro GPU rendered both 1280Ã—720 images: 1,843,200 checked pixels,
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

Vulkan rendered two 1280Ã—720 images, checked all 1,843,200 pixels, channel sum
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

Next: accept the corrected guest image import on the phone, implement moving Metal
presentation and guest WSI/compositor/OpenGL, then integrate authenticated SteamOS, actual ARM
Steam/CEF, Game Mode/desktop and FEX/Proton through the coverage ledger.
Native host/Metal optimization does not remove guest TCG translation costs.
**Steam usable under 60 seconds and Hollow Knight 60â€“80 base rendered FPS at
1280Ã—720, including sustained thermal/frame-pacing measurements, are unverified.**


## Current guest graphics implementation

A fresh graphics-capable Linux 6.12.111 kernel now includes generic PCI, virtio
PCI/MMIO and DRM virtio-GPU. It is kept separate from the phone-verified CPU
kernel and uses the same source-pinned Linux/BusyBox archives. Hosted ARM TCG
[run 37067848259](https://github.com/aghjkshdsj/My-pc/actions/runs/37067848259),
source `6ab4df9f78ec307e026f378658673efa3ebeeec2`, passed real DRM driver/version
queries, 1280Ã—720 resource allocation/map, CPU pattern verification, transfer
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
stager/source collector passed physical-iOS cross-compilation. The adapter
explicitly selects ANGLE Metal and GLES; its upstream headless readback is a
correctness diagnostic, not the planned steady-state presenter. The separate
EGL-enabled virgl/Venus recipe consumes the accepted ANGLE build. Its first
actual compile produced the EGL renderer object, but the final audit incorrectly
expected a numeric value for a Meson boolean macro. The audit now accepts only
the enabled bare-define or value-1 forms and checks the actual EGL compile command.
The corrected compile and audit passed run 37078312649, source
`7281f4759ba47cfcfc492a4093ee56b5bf9730d9`, against ANGLE run 37077105285.
Receipt: `evidence/primary/hosted-ios-gl-venus-build.json`. This retains EGL,
GLES, epoxy and virgl/Venus engines with complete corresponding source; it is
not a phone loader or graphics result. QEMU GPU build 37078645613 passed at source
`56f2522eed4509fe2010d2250eaa569dd503c660`, including actual virtio-GPU GL/Venus,
EGL headless objects, public framework import closure and all corresponding source.
The explicit ANGLE root context requests GLES 3. Receipt:
`evidence/primary/hosted-ios-gpu-engine-build.json`. These are native compilation
checks, not phone context creation or guest graphics evidence.

A new ARM Linux Mesa 26.2.2 recipe pins the official 68,533,264-byte archive to
SHA-256 `eeb29ca7e56cfaa8e8a79538dcf834e3b18e501c31bef5145e959ea437cc4216`.
Only virgl/Venus drivers are selected. Hosted run 37074804870, source
`9ddc641f25d83a230affb90c7e59174a041bde30`, passed actual ARM64 ELF library,
unified Gallium/compiled-virgl, ICD and shader compilation checks. The exact new
Venus ICD correctly failed physical-device enumeration with Vulkan -3/exit 3 in
a verified separate mount namespace with no DRM device nodes. Two earlier audit
failures caught an obsolete alias assumption and the host DRM-directory precondition;
both are retained. Receipt: `evidence/primary/hosted-guest-mesa-build.json`.
This standalone artifact is guest userspace, not a complete initramfs or SteamOS image. The full Mesa
source and exact recipe/settings are retained. External Linux loader/libraries
and their package/source versions are recorded separately. The complete disposable
payload described below closes its runtime lookup/source packaging. No guest
shader or phone graphics result is implied by this compile/negative test.

A fresh combined graphics initramfs now stages the exact Mesa userspace, resolves
its ARM64 dynamic loader/DSO closure ahead of system libraries, and retains exact
Ubuntu package/source versions, copyright notices, source archives and signed APT
metadata. Run 37078645537 booted this runtime with both a 2D-only GPU and no GPU:
all Linux ABI checks passed, and the exact Venus ICD rejected both with Vulkan -3.
Its final source packaging failed on the root-owned APT lock. The corrected full
build passed run 37079133580, source `cb99fc4740385ddcb37119bbc164d5671ea61ce0`.
The source archive retains exact package sources/configuration and signed index
metadata. A read-only audit in run 37079667769 verified the artifact hashes and
printed its complete receipt: `evidence/primary/hosted-guest-gpu-payload.json`.
The 10,049,925-byte initramfs has SHA-256
`ef228a4f89de1d4e49b5a6ab88856448dc513f3ac92d242c39dc040ad9b019e0`.
These are real Linux runtime boots with negative GPU controls, not shader results.

Phone host-memory import, guest Mesa/Venus shader draws and moving Metal
presentation remain unfinished. The new
[Linux guest Vulkan gate 1 / build 4000011 IPA](https://github.com/aghjkshdsj/My-pc/releases/download/steamos-ios-guest-gpu-gate-1/MyPCSteamOS-Guest-GPU-Gate.ipa)
passed run 37089500068 at source `d87e07204afa9ec64503706f3c601e1f491f8737`.
It includes the exact nine-framework native dependency closure and complete
disposable Linux graphics payload. The public 24,092,262-byte IPA was independently
downloaded and checked: SHA-256
`bb57e9087563d4da41548695dd30036c48c27629aa105e1bcc5ad182e44a296b`,
complete ZIP CRC, physical ARM64 iOS Mach-O/imports, source/build identity,
signing-compatible code sections and exact guest/shader hashes. Actual Release
Xcode compilation, 43 Python evidence tests, 28 production native receipt checks
and crash/reopen/export tests passed. Receipt:
`evidence/primary/ios-guest-vulkan-prerelease.json`.
Its new Run Linux guest Vulkan gate requires a fresh process, fresh JIT,
fresh nonce, passing Linux ABI, real virtio-GPU 3D/blob/host-visible/context
capabilities and two non-software Vulkan shader phases with full pixel checks.
Native rejection fixtures exercise the production receipt parser; they are not
device results. The report records executed_tests so saved earlier successes
cannot count as freshly executed tests. Guest pixels cannot independently prove
host Metal completion, host-memory import, zero-copy, presentation or gameplay.
All of those gates remain unverified.

Build 4000011's subsequent phone attempt failed at missing EGL-headless backend,
as recorded above. The owner has now run the replacement build 4000012: Linux
and DRM memory checks passed, while Vulkan initialization failed as described
above. This is preserved historical build 4000012 analysis; current device procedure is
in the build 4000018 record, without repeating historical rejected configurations.
See `docs/GUEST-GPU-FAILURE.md` for the exact protocol decoding, reviewed pinned
source and unresolved cause. No guest Vulkan pass, Steam installation or
gameplay is inferred from the partial result.
The private offline `tools/verify_guest_gpu_report.py` checks exact IPA/source,
executed test identity, engine code, fresh serial/DRM/shader receipts and unchanged
product limitations. Six guest report rejection-fixture tests and four backend
build-audit tests now pass within the 53-test suite. These are additional parser
and build checks, not GPU/device results.
