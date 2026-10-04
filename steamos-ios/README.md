# My-pc SteamOS iOS â€” fresh bring-up

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
This corrects an identified registration-lifetime bug. The corrected phone build
and elimination of delayed crashes remain unverified. It is a crash-fix candidate,
not a new desktop/game/performance milestone. Keep the completed screen-test
result in the foreground for 30 seconds, then share report and saved logs.
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


This source directory and `MyPCSteamOS.xcodeproj` are new. The project links no
Madeira, previous VM app, Wine, FEX or previous native-preview code. Existing
projects, disks, games and account data remain preserved. Later CPU-gate
releases embed source-built upstream QEMU/iOS engine libraries through a new
adapter; no previous application implementation is an input.

The owner-selected [DroidDeck blueprint](docs/DROIDDECK-BLUEPRINT.md) now defines
Steam/desktop/controller/component flows and the complete feature mapping. All
735 archive files are inventoried; Android's PRoot/Adreno/SurfaceControl path
requires new iOS adapters and is not a direct port. The requested actual
SteamOS ARM environment remains the architecture.

Current package: **[build 4000020 / guest image gate 11](https://github.com/aghjkshdsj/My-pc/releases/download/steamos-ios-guest-gpu-gate-11/MyPCSteamOS-Guest-GPU-Gate.ipa)**.
24,352,061 bytes, SHA-256
`580244c2dd508fa0e8ba990c4d6035d1b1755530125229101cabc81ff872e0fd`.
Source `85314b25222cf3fe14058ead85cc7869d9474e4b`.
[Sources, checksums and validation](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-11).
Actual Release ARM64 iOS compilation, 87 Python checks, 28 native guest receipt
checks, 27 completion-ledger checks, 56 image-receipt checks and recovery/capture
fixtures passed. The production budget tests preserve two distinct resource
readbacks across repeated callbacks and reject 14 invalid event/layout cases.
Shared colour-order fixtures retain 1,843,200 synthetic pixel checks. These
fixtures cannot establish a new phone import pass.

The native image diagnostic now consumes each immutable guest resource once.
Reinstallation with a newer display generation does not consume another readback.
Changed format/layout is rejected. Both receipt validators still require every
installation's valid flush/disable lifecycle, distinct phases/resources, first
flush generations, exact device/layout/pixels/fences and cleanup. Two copies of
the first image cannot pass. The exact successful BGRA/XRGB guest, kernel,
initramfs, engine bundle and all ten native framework binaries are preserved
byte-for-byte from independently verified build 4000019.

Published IPA, source, checksum and verification were independently downloaded
and checked. All 15 changed source files match. Image import on the phone, moving
presentation, full SteamOS and game targets remain unfinished. Owner results and
detailed analysis stay in ignored local `evidence/device/`, excluded from uploads.
Install with iLoader; in a fresh process enable JIT through StikDebug, pass ARM64
JIT check and run Linux image import gate once. Keep foreground and share the
resulting device report. See [build 4000020 details](docs/GPU-GATE-4000020.md) and
[image import/presentation acceptance](docs/PRESENTATION-GATE.md).

Preserved format diagnostic: [build 4000019 / gate 10](docs/GPU-GATE-4000019.md).
Preserved modifier diagnostic: [build 4000018 / gate 9](docs/GPU-GATE-4000018.md).
Preserved image diagnostic: [build 4000017 / gate 8](docs/GPU-GATE-4000017.md).
Preserved recovery diagnostic: [build 4000016 / gate 7](docs/GPU-GATE-4000016.md).
Earlier packages, source and user data are retained.

Preserved observer package: [build 4000015 / guest Vulkan gate 5](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-5),
source `6aa8dc6a2be44c7941c1e89ad25e378d31485249`, 24,311,595 bytes,
SHA-256 `9e625eb1f51f6f8a20578fa0e8fc012b0bf0a939c6649515abdbc0409bbf8bda`.
Its independently checked observer source and original 62/28/25 fixture/build
results remain preserved. [Observer implementation](docs/GPU-GATE-4000015.md).

Preserved earlier package: **[Linux guest Vulkan gate 4 / build 4000014](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-4)**.
24,302,427 bytes, SHA-256
`5f01aec63be5923d87b3eabf8e0a91c0e0e44853cb60a92e22b53281bfb20dd6`.
Source `696f3b62d0064b8c33d6e34e14760cbc7558ceb6`.
[Sources, checksums and validation](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-4).
The host now explicitly selects a checked app-private file directory for native
renderer communication. The renderer creates exclusive private files, unlinks
their names immediately and retains upstream mapping/error behavior. Actual
native Darwin allocator tests, 54 evidence tests, 28 native receipt checks,
recovery tests and physical ARM64 iOS Release compilation passed. Independent
public download verified the IPA and the newly changed source archives, including
the actual helper, patch, tests and original renderer source. Package checks
are separate from device acceptance; owner reports and detailed matching analysis
are retained locally. Use the current build for the native completion test. See
[build 4000014 details](docs/GPU-GATE-4000014.md).

Preserved earlier package: **[Linux guest Vulkan gate 3 / build 4000013](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-3)**.
24,300,637 bytes, SHA-256
`b183d0ccf406d15bb9390bfa421178098f8686f0e00649c7d10a989ac397ecfe`.
Source `8ae27c43baa43f5c193ede199725eacd2581b753`.
[Sources, checksums and validation](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-3).
The preliminary Linux DRM texture request now uses the correct render-target
bind. The renderer/QEMU report actual failure stage, errno and context/blob
results, and the normal device report includes a bounded host log tail.
Actual native recovery tests, 53 evidence tests, 28 production receipt checks,
Release physical-iOS ARM64 compilation and independent public IPA verification
passed. These package checks establish no guest shader or game result. See
[build 4000013 details](docs/GPU-GATE-4000013.md).

Preserved earlier package: [build 4000012 / guest Vulkan gate 2](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-2),
source `aa2f8ccfb15eb53a96f70775be8e83ca0c5703b2`, 24,292,269 bytes,
SHA-256 `256da95463a5594cc41b93f1f2a64a096418ce39ef7f2471af4ffb39c1dcdbf8`.
It remains verifiable with its historical engine/guest pins. Existing partial
Linux/DRM evidence does not establish guest Vulkan rendering.

Historical package: **[Linux guest Vulkan gate 1 / build 4000011](https://github.com/aghjkshdsj/My-pc/releases/download/steamos-ios-guest-gpu-gate-1/MyPCSteamOS-Guest-GPU-Gate.ipa)**.
24,092,262 bytes, SHA-256
`bb57e9087563d4da41548695dd30036c48c27629aa105e1bcc5ad182e44a296b`.
Source `d87e07204afa9ec64503706f3c601e1f491f8737`.
[Source archives, exact dependencies, checksums and verification](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-1).
Actual Release iOS ARM64 compilation, 43 Python evidence tests, 28 native
production receipt checks and recovery tests passed. The public IPA was
independently downloaded and verified for ZIP CRC, exact source/build/hash,
nine physical-iOS native frameworks, executable identities and guest payloads.
The owner subsequently reported an app closure: QEMU exited because egl-headless
was unavailable before Linux boot. The exact engine configuration had Pixman
disabled. The corrected engine explicitly enables Pixman and audits the real
backend object/export. Build 4000012 passed compilation and package verification
with a native backend registration preflight. Do not repeat build 4000011 as the positive GPU gate.
Those historical package/control results did not establish the Linux guest
Vulkan shader path. Current per-device acceptance is recorded separately in
the local device coverage record. See [historical failure analysis](docs/GUEST-GPU-FAILURE.md).

The requested product remains an actual SteamOS ARM environment running Valve's
Linux ARM Steam and FEX games. It is **unfinished**. The first separate IPA is
`My-pc SteamOS Probe` (`com.aghjkshdsj.mypc.steamos.probe`, build 4000001).
It tests host Metal computation/readback, a small temporary storage file and a
fixed ARM64 JIT stub after StikDebug. None is a Linux boot or gameplay test.
The subsequent **Linux-gate-2** IPA, build 4000003, bundles the CPU engine and
source-built Linux 6.12.111 / BusyBox 1.38.0 initramfs. It is a disposable Linux
execution test, not a substituted SteamOS product. Its historical phone failures
led to the build 4000007 correction and verified phone boot described below.

[Download the verified Linux-gate-2 IPA](https://github.com/aghjkshdsj/My-pc/releases/download/steamos-ios-linux-gate-2/MyPCSteamOS-Linux-Gate.ipa)
(7,999,301 bytes, SHA-256
`d7eb3db958794bcf653b10e0d7b199a745ce61ba1cb2b1dae6169b61d5652430`).
[Exact source, checksums and verification](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-linux-gate-2).

Phone-verified CPU baseline: [Linux-gate-7 / build 4000007 IPA](https://github.com/aghjkshdsj/My-pc/releases/download/steamos-ios-linux-gate-7/MyPCSteamOS-Linux-Gate.ipa),
with reopen-and-share recovery, StikDebug activation, retained JIT mappings and
a 32 MiB split-WX engine cache. 8,075,687 bytes, SHA-256
`ec52d95d65e434911d21e77e218649d5da99786342afa9b7c7ebbda72b1e411c`.
Source commit `f18e3c3d91ba8bdf6b55c6e6cb7a33db4ea65841`.
[Corresponding source and verification](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-linux-gate-7).
Hosted recovery tests and iOS compilation passed; the public IPA was independently
downloaded and checked. Build 4000007 passed actual iPhone native JIT and Linux
kernel/ABI checks. The recorded 691.06 ms kernel-plus-test run is software TCG
emulation, not SteamOS startup, hardware virtualization or game performance.
Build 4000010 packages a native Vulkan-to-Metal offscreen shader gate through
the corrected source-built MoltenVK engine. Actual iOS compile, recovery and
31 evidence tests passed; the independently downloaded IPA passed identity,
payload, dependency and CRC checks. The build 4000010 owner-supplied iPhone report
also passed the native Vulkan-to-Metal offscreen gate: Apple A17 Pro GPU, two
1280Ã—720 images, 1,843,200 pixels, zero mismatches and the exact channel sum.
The 497.20 ms complete native test is not game FPS. Phone validation layers
were not enabled; source/report consistency is not cryptographic attestation.
Linux guest graphics and moving presentation remain separate unfinished gates.

[Phone-verified native graphics baseline: Linux-gate-10 / build 4000010](https://github.com/aghjkshdsj/My-pc/releases/download/steamos-ios-linux-gate-10/MyPCSteamOS-Linux-Gate.ipa).
9,528,852 bytes, SHA-256
`3d11c3815b5108406019074787975d53426edb21fa085fc61643a378abf69dba`.
Source `208647c2f7c18f32fcf894771756c0fbeb487374`.
This host graphics test needs no JIT and has already passed on the owner's
phone. Corresponding source and verification accompany the prerelease.
This supersedes build 4000008, whose phone report failed the whole-file MoltenVK
hash check before loading the renderer. The corrected gate verifies executable
code identity independently of iLoader's signing metadata; complete original
unsigned IPA and shader hashes remain exact. The correction has passed compilation,
offline verification and signing-metadata simulation; build 4000010 subsequently
passed native offscreen phone rendering.
The returned build 4000009 phone report passed engine identity and draw exit 0,
but its pixel/renderer diagnostic was empty and was rejected as incomplete proof.
Build 4000010 saves a dedicated fsynced JSON receipt and preserves it in recovery
sharing, independently of engine stdout/stderr. Its actual ARM64 iOS compile,
31 evidence tests, recovery/export tests, five real hosted Vulkan adapter cases
and independent public IPA checks passed. Physical phone native offscreen
acceptance passed separately. Linux guest graphics and moving presentation remain open.

The owner confirmed iPhone 15 Pro Max, iOS 27.0.1, iLoader and StikDebug on
2026-10-02. The probe records the actual OS build, page size, code-signing state,
Metal device, memory, thermal state and Low Power Mode. Controller enumeration
is recorded but is not reported as a controller test.

Read [architecture and gates](docs/ARCHITECTURE.md),
[component coverage](docs/COMPONENTS.md), [performance measurements](docs/PERFORMANCE.md)
and [upstream provenance](docs/PROVENANCE.md).

## Device step

Earlier device reports and saved diagnostics have been received and analyzed
locally. Use build 4000016 for future diagnostic attempts; older packages and reports are
preserved. The current normal report includes a bounded host engine log tail.

For a new attempt after a fix, use the verified build linked above.
Install it with iLoader. Close/relaunch, use **Enable JIT in StikDebug**,
confirm the universal.js request and return. Run **Run Linux guest Vulkan gate**
once, before the older Linux kernel button.
Keep the app foreground for up to three minutes and use **Share device report**
to return its JSON; **Share saved diagnostic logs** also retains the complete
serial and engine stages. If it closes, reopen and use the recovery Share logs
prompt. Close/relaunch and enable JIT for the new process before another Linux
attempt. Each CPU/GPU QEMU test uses one process initialization. An interrupted
run cannot pass. Guest pixel correctness, independent host Metal completion,
host-memory import, moving presentation and game performance are separate gates.
No account credentials or Steam tokens are collected. Reports remain in the
new app's Documents directory and are never automatically uploaded.

Crash recovery builds save a pending-test marker before JIT or engine execution,
plus fsynced native stage logs and available engine stdout/stderr. Reopen after
an interrupted test to see **Previous test stopped â€” share logs**. Choose
**Share logs** to export one diagnostic JSON. **Later** and cancelling the share
sheet preserve the files; **Share saved diagnostic logs** stays available.
The export includes bounded known probe reports and kernel serial logs only.
A pending marker cannot distinguish a crash, iOS termination and force-close;
it is not an iOS crash stack. Logging does not itself fix a JIT or Linux failure.

The updated JIT implementation matches `universal.js`: prepare RX regions through
the external debugger, create a separate writable alias, configure the pinned
QEMU engine's legacy-region callback through the universal command protocol,
then detach after QEMU's initial TCG allocation. The button targets the current
PID and actual signed bundle ID. Opening StikDebug is not reported as successful
JIT; the native stub must execute and return 42. Fresh and repeated retained-region
execution passed on the phone in build 4000007. It does not change the Linux/SteamOS architecture or add a StikJIT
framework/helper or pairing file to the app.

## Build

On a Mac with Xcode's iOS SDK:

```sh
python3 steamos-ios/tools/generate_project.py
xcodebuild -project steamos-ios/MyPCSteamOS.xcodeproj -scheme MyPCSteamOSProbe \
  -configuration Release -sdk iphoneos -destination generic/platform=iOS \
  -derivedDataPath steamos-ios/out/xcode CODE_SIGNING_ALLOWED=NO \
  MPC_SOURCE_COMMIT="$(git rev-parse HEAD)" build
```

CI builds and verifies exact ARM64 iOS host-probe, Linux-gate and guest-GPU IPAs,
each with accurate scope, checksums and applicable corresponding source.
The Linux-gate-10 baseline includes a separate native offscreen Vulkan diagnostic
and a CPU-only disposable kernel. Guest-GPU build 4000016 separately includes
the GPU-capable kernel, Mesa Venus runtime and native renderer transport;
its phone Vulkan shader acceptance remains unfinished.
Device signing is supplied by iLoader. JIT must be verified after re-signing.

The private local archive audit hashes and scans every ZIP file without
extracting or running any attached script. `evidence/archive-summary.json` and
`evidence/archive-files.csv` contain distributable inventory receipts.
