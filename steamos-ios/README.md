# My-pc SteamOS iOS — fresh bring-up

This source directory and `MyPCSteamOS.xcodeproj` are new. The project links no
Madeira, previous VM app, Wine, FEX or previous native-preview code. Existing
projects, disks, games and account data remain preserved. Later CPU-gate
releases embed source-built upstream QEMU/iOS engine libraries through a new
adapter; no previous application implementation is an input.

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
Build 4000009 packages a native Vulkan-to-Metal offscreen shader gate through
the corrected source-built MoltenVK engine. Actual iOS compile, recovery and
30 evidence tests passed; the independently downloaded IPA passed identity,
payload, dependency and CRC checks. Its physical graphics test is pending.
Linux guest graphics and moving presentation remain separate unfinished gates.

[Latest graphics-bearing IPA: Linux-gate-9 / build 4000009](https://github.com/aghjkshdsj/My-pc/releases/download/steamos-ios-linux-gate-9/MyPCSteamOS-Linux-Gate.ipa).
9,528,005 bytes, SHA-256
`ef2a64948b06c2d81712dd980d6eb71bcd374efb1ef64efb0e308fd0bd86a05b`.
Source `2d557a6a8bc91bf21b77013558e16977684819eb`.
Install with iLoader and run **native Vulkan → Metal check** once; no JIT is
needed for this host graphics test. Share its saved device report or recovery
logs. Corresponding source and verification accompany the prerelease.
This supersedes build 4000008, whose phone report failed the whole-file MoltenVK
hash check before loading the renderer. The corrected gate verifies executable
code identity independently of iLoader's signing metadata; complete original
unsigned IPA and shader hashes remain exact. The correction has passed compilation,
offline verification and signing-metadata simulation, with phone rendering pending.
The returned build 4000009 phone report passed engine identity and draw exit 0,
but its pixel/renderer diagnostic was empty and was rejected as incomplete proof.
Build 4000010 is prepared to save a dedicated fsynced JSON receipt and preserve it
in recovery sharing. Its iOS compile, real hosted draw regression and release are pending.

The owner confirmed iPhone 15 Pro Max, iOS 27.0.1, iLoader and StikDebug on
2026-10-02. The probe records the actual OS build, page size, code-signing state,
Metal device, memory, thermal state and Low Power Mode. Controller enumeration
is recorded but is not reported as a controller test.

Read [architecture and gates](docs/ARCHITECTURE.md),
[component coverage](docs/COMPONENTS.md), [performance measurements](docs/PERFORMANCE.md)
and [upstream provenance](docs/PROVENANCE.md).

## Device step

Install the probe alongside the older apps using iLoader. Run **Metal and storage
probes**, use **Enable JIT in StikDebug** in the updated app, confirm StikDebug's
request if prompted, return here and run **ARM64 JIT check**.
Then run **Linux kernel gate**, keep the app foreground for up to three minutes,
and use **Share device report** to return the JSON. Close/relaunch before another
Linux boot. If JIT execution terminates the
app, retain the first report and report the failure; do not call it a success.
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

CI builds and verifies exact ARM64 iOS host-probe and Linux-gate IPAs,
each with accurate scope, checksums and applicable corresponding source.
The latest Linux-gate IPA includes a separate native offscreen Vulkan diagnostic;
the disposable Linux kernel remains CPU-only without guest GPU transport.
Device signing is supplied by iLoader. JIT must be verified after re-signing.

The private local archive audit hashes and scans every ZIP file without
extracting or running any attached script. `evidence/archive-summary.json` and
`evidence/archive-files.csv` contain distributable inventory receipts.
