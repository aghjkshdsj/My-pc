# My-pc SteamOS iOS — fresh bring-up

This source directory and `MyPCSteamOS.xcodeproj` are new. The project links no
Madeira, previous VM app, Wine, FEX or previous native-preview code. Existing
projects, disks, games and account data remain preserved. Later CPU-gate
releases embed source-built upstream QEMU/iOS engine libraries through a new
adapter; no previous application implementation is an input.

Current test: **[Linux guest Vulkan gate 2 / build 4000012](https://github.com/aghjkshdsj/My-pc/releases/download/steamos-ios-guest-gpu-gate-2/MyPCSteamOS-Guest-GPU-Gate.ipa)**.
24,292,269 bytes, SHA-256
`256da95463a5594cc41b93f1f2a64a096418ce39ef7f2471af4ffb39c1dcdbf8`.
Source `aa2f8ccfb15eb53a96f70775be8e83ca0c5703b2`.
[Corresponding sources and verification](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-2).
The corrected engine passed its Pixman/configuration, actual headless object and
library-export audits. The app checks real backend registration before boot.
Release compilation, 53 evidence tests, 28 native receipt checks and recovery
tests passed. Independent public redownload verified all ten native frameworks,
their exact code identities, payload hashes, source/build and ZIP CRC.
The returned phone report now verifies Linux boot/ABI and the virtio-GPU
allocation/map/CPU-pattern/transfer-ioctl checks. Guest Vulkan fails before
rendering at shared-resource creation; the engine shuts down normally.
Positive phone guest graphics, independent Metal completion/import, presentation
and SteamOS/game performance remain **unverified**. The next needed evidence is
**Share saved diagnostic logs** for the existing attempt, which includes the
host engine output absent from the normal report.

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
The new Linux guest Vulkan shader path is **unverified on the phone**. Build
4000012's partial Linux/DRM success and older native host graphics results do
not establish it. See [current failure analysis](docs/GUEST-GPU-FAILURE.md).

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
1280×720 images, 1,843,200 pixels, zero mismatches and the exact channel sum.
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

The latest build 4000012 device report has already returned Linux/ABI/DRM success
and a failed guest Vulkan initialization. Use **Share saved diagnostic logs**
now to export that same attempt's host engine output; a rerun is unnecessary.
The normal **Share device report** file contains the guest serial failure but
does not include this host output. The next fix depends on that distinction.

For a new attempt after a fix, use the verified build linked above.
Install it with iLoader. Close/relaunch, use **Enable JIT in StikDebug**,
confirm the universal.js request and return. Run **ARM64 JIT check**, then
**Run Linux guest Vulkan gate** once, before the older Linux kernel button.
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
an interrupted test to see **Previous test stopped — share logs**. Choose
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
and a CPU-only disposable kernel. Guest-GPU build 4000012 separately includes
the GPU-capable kernel, Mesa Venus runtime and native renderer transport;
its phone Vulkan shader acceptance remains unfinished.
Device signing is supplied by iLoader. JIT must be verified after re-signing.

The private local archive audit hashes and scans every ZIP file without
extracting or running any attached script. `evidence/archive-summary.json` and
`evidence/archive-files.csv` contain distributable inventory receipts.
