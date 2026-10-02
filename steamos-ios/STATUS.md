# Verified state and next work — 2026-10-02

The complete user objective is **not complete**. No architecture substitution
was approved or adopted. The owner confirmed iPhone 15 Pro Max / iOS 27.0.1,
iLoader signing and StikDebug JIT. A private owner-supplied native host report
has been received and checked; native Metal/CPU/storage correctness passed.
The owner reports termination during JIT and Linux checks, with no saved result
for either. The cause, Linux boot, guest Metal transport and gameplay performance
remain unverified. Raw device evidence is kept outside the public upload allowlist.

## Preserved state and fresh implementation

- Read the complete handoff, all four archive docs, core build/client/session
  scripts, previous performance/build reviews, graphics implementation and
  filtered Dokimon logs. Attached scripts were reference material and were not run.
- Inspected the local no-commit/no-remote Git state and remote main/branches/CI.
  Previous projects, apps, user disks, credentials and game data remain preserved.
- New `steamos-ios` source/Xcode target and `codex/steamos-ios-fresh` branch,
  based on main `3aa9fdb4b72d7127c4fe9c077aaf613937da293f`. No Madeira,
  old VM application or current native-preview code is a build input.
- All 3,672 archive files have CRC, size, SHA-256 and component assignments.
  Inventory/source-isolation checks passed; whole-vendor-source semantic audit
  is not claimed. The component ledger covers every archive group and service.
- The owner explicitly approved ongoing source/tests/workflow uploads, builds
  and probe prereleases on this branch. Private phone reports, old projects,
  credentials and user games remain excluded.
- New native probes record device/build/pages/signing, five checksummed CPU trials,
  a 720p Metal compute/readback result and a unique temporary 32 MiB storage test.
  They do not demonstrate a guest game or sustained performance.

## Verified builds and Linux-gate prerelease

[Linux-gate-2 IPA](https://github.com/aghjkshdsj/My-pc/releases/download/steamos-ios-linux-gate-2/MyPCSteamOS-Linux-Gate.ipa):
build 4000003, source `38f401c524f98bc000002cdc81bb000c9502f1e3`,
7,999,301 bytes, SHA-256
`d7eb3db958794bcf653b10e0d7b199a745ce61ba1cb2b1dae6169b61d5652430`.
[Release sources and receipts](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-linux-gate-2).

The independently downloaded public IPA passed complete ZIP CRC, ARM64 physical
iOS Mach-O, bundle/source identity, all four engine dependency resolutions and
kernel/initramfs SHA-256 checks. Packaging success does **not** mark a phone gate
passed. Its disposable initramfs is not SteamOS or an architecture substitution.

| Verified result | Evidence | Limit |
|---|---|---|
| Fresh Release ARM64 iOS host/adapter/CPU probe build | [37015555146](https://github.com/aghjkshdsj/My-pc/actions/runs/37015555146) | Compile/package, not phone execution |
| Source-built QEMU 10.0.12-utm iOS TCG engine with required exports | [37014232362](https://github.com/aghjkshdsj/My-pc/actions/runs/37014232362) | No Hypervisor or GPU; four needed frameworks |
| Hosted ARM Linux kernel ABI test | [36966305447](https://github.com/aghjkshdsj/My-pc/actions/runs/36966305447) | Hosted Linux 6.8, not an iPhone |
| Source-built Linux 6.12.111 / BusyBox 1.38.0 kernel ABI gate | [37014232445](https://github.com/aghjkshdsj/My-pc/actions/runs/37014232445) | Hosted TCG; kernel/ELF ARM64, 4 KiB pages, all four ABI checks and exit marker passed |
| GL shader correctness and software-renderer rejection | [37014783465](https://github.com/aghjkshdsj/My-pc/actions/runs/37014783465) | Hosted llvmpipe: 1,843,200 pixels, zero errors/mismatches; software rejected, no Metal claim |
| Four-framework Linux-gate-2 assembly/publication | [37016891655](https://github.com/aghjkshdsj/My-pc/actions/runs/37016891655) | Independent public IPA verification passed; phone result pending |
| Evidence consistency/rejection tests | 13 local unit tests and source-isolation check passed | Synthetic fixtures only, never counted as device evidence |

The new `Host/LinuxGate.mm` requires native JIT, verifies bundled payloads,
loads the source-built QEMU library and boots a new nonce in a generic ARM virt
machine: TCG, 2 vCPUs, 512 MiB, no display/network/persistent disk. Serial and
pending receipts survive engine failure. One initialization per process; close
and relaunch after timeout or before another boot.

Resolved build failures: extern-C linkage; gettext/CoreFoundation/iconv static
linking (restored shared dependencies); BusyBox init exit marker (explicit
BusyBox echo). No failed check was waived. Corresponding engine/kernel/BusyBox
source, configs, patches, recipes and applicable notices accompany the release.

## Resolved external metadata, unfinished full inputs

- Valve stable ARM manifest version **1788652215** is pinned with SHA-256.
  All **35** package URLs returned expected HEAD sizes, totaling
  **1,008,581,976 bytes**. The complete client has not been downloaded, hash/ZIP
  verified, installed or launched. Manifest signature authentication remains open.
  See `evidence/primary/steam-package-plan.json`.
- Official ARM rootfs metadata **20260921.6090922 / 0.5.0** is resolved.
  The pinned RAUC bundle contains `rootfs.img.caibx`: 88,387 chunk records,
  reconstructed size **10,737,418,240 bytes**, image SHA-256
  `5c53ff2ed7dc78f313a19fc9224aa07e7fb63271b811a4ada295441a0361e6a8`.
  Three downloaded/decompressed chunk samples passed actual **SHA-512/256** checks.
  [Metadata run 37018663739](https://github.com/aghjkshdsj/My-pc/actions/runs/37018663739).
  See `evidence/primary/valve-rootfs-metadata.json`.
- Full rootfs reconstruction, all-chunk/image verification, Valve RAUC CMS trust,
  generic-virt boot compatibility and package/runtime integration remain open.
  No Valve binary, rootfs, Steam account or game depot was published in our release.
- Apple's current Hypervisor/Virtualization metadata is macOS-only; no supported
  public iOS hardware-virtualization path has been demonstrated. StikDebug is
  a JIT precondition, not EL2 access. The current Linux route is software TCG;
  FEX inside it adds x86-to-guest-ARM translation.
- Current upstream Darwin virgl/Venus shared-memory emulation is a reuse candidate,
  not a verified graphics bridge. Exact GL/Vulkan/Metal presentation and feature
  tests are still required. Linux gamescope, Plasma, Steam/CEF, FEX/Proton,
  audio/input/storage/downloads/overlays/plugins are unfinished.

## Required phone evidence and next implementation

Crash recovery implementation passed hosted abrupt-exit tests and an actual
ARM64 iOS build in [37021915308](https://github.com/aghjkshdsj/My-pc/actions/runs/37021915308)
and was published as Linux-gate-3 / build 4000004. It has a durable pending
marker before unsafe calls, fsynced stage/output capture, a reopen Share logs
prompt, retained logs after Later/cancel and manual diagnostic sharing. Hosted
abrupt-exit/recovery and iOS compile/package checks are required before release;
the popup still needs verification on the phone. This change instruments the
JIT/Linux failure and does not claim that its cause is fixed.

Builds 4000005/4000006 add Enable JIT in StikDebug with actual bundle ID/PID
and universal.js, observed get-task-allow/current debugger checks, RX/writable
alias preparation through the universal protocol, a fixed callback for the
pinned QEMU allocator's legacy 0x69 region breakpoint, and detach after QEMU's
initial code allocation. The supplied old host report contained no JIT/Linux
receipt. The previous RW-to-RX probe and QEMU breakpoint mismatch are source
findings, not a proven crash diagnosis. Updated phone JIT/boot results are needed.

Final [Linux-gate-5 / build 4000006](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-linux-gate-5)
passed [run 37024755837](https://github.com/aghjkshdsj/My-pc/actions/runs/37024755837):
13 evidence tests; real hosted subprocess abrupt exit with fsynced stage/output;
reopen/completed/timeout marker behavior; cancelled/retained exports; corrupt and
stale markers; path/symlink exclusion; bounded tails; exact StikDebug URL fields;
and actual ARM64 iOS Release compilation. The share sheet waits for the recovery
alert dismissal and prevents duplicate requests.

Independent public IPA verification: 8,069,591 bytes, SHA-256
`adc3e7abd2afc736bd424ed66bd6a32cdcdbd9f6921deefc5dc56225055d100a`,
source `dac0d7d6d4f8c10100e986cf67e9adc3668e792b`. Complete ZIP CRC, physical-iOS
ARM64 executable/frameworks, dependency closure and bundled kernel hashes passed.
The three compiled universal ABI wrappers also contain their exact ARM64
command/breakpoint/return sequences. These build checks are not phone JIT,
Linux boot, UI-popup or gameplay proof. No private report was uploaded.

Install Linux-gate-5 / build 4000006 with iLoader. Run Metal/storage/native CPU probes,
tap **Enable JIT in StikDebug**, confirm its request for **My-pc SteamOS Probe**,
return to the app, run the JIT check, then **Run Linux kernel
gate** in the foreground for up to three minutes. Use **Share device report** to
return the JSON. If the app terminates, preserve its new `LinuxGate-*` folder's
serial/pending report and reopen to use **Share logs**; do not report a successful boot.

`tools/verify_device_report.py` compares private owner-supplied evidence with the
exact verified IPA, checks OS/source/payload/nonce/serial/engine/ABI consistency
and preserves all SteamOS/game/performance gates as false. It is not cryptographic
remote attestation and does not upload reports. Native-versus-guest microbenchmark
ratios, when available, are not gameplay FPS.

After the physical CPU gate: debug any phone loader/JIT/kernel failure, build
the upstream graphics engines through fresh adapters, prove guest GL and Vulkan
to Metal including moving presentation, then integrate authenticated SteamOS,
actual ARM Steam/CEF, Game Mode/desktop and FEX games. Follow the component and
performance ledgers through 720p base-frame and 20-minute thermal measurements.
**Steam usable under 60 seconds and Hollow Knight 60–80 base FPS are unverified.**

## Vulkan diagnostic preparation

The fresh guest Vulkan diagnostic renders two RGBA8 images at 1280×720 using
vertex/fragment shaders, a render pass and explicit image/copy/host-read barriers.
It compares all 1,843,200 pixels and independently checks the channel sum. It
records device extensions, selected features/limits, format and memory flags,
and validation errors. Optional portability enumeration/subset support is handled.
It has no window/swapchain or transport; Metal/presentation/game claims stay false.
The hosted ARM pipeline uses lavapipe with synchronization validation and requires
exit 20 when software is offered as acceleration. This workflow is newly prepared;
its compile, rendering and rejection result are pending. No new physical phone
JIT/Linux report was available at this checkpoint.
