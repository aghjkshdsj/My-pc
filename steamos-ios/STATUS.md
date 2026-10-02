# Verified state and next work — 2026-10-02

The complete user objective is **not complete**. No architecture substitution
was approved or adopted. The owner confirmed iPhone 15 Pro Max / iOS 27.0.1,
iLoader signing and StikDebug JIT. Physical phone results are still pending.

- Read the complete handoff and all four archive docs, core build/client/session
  scripts, previous performance/build reviews, graphics implementation and
  filtered Dokimon log evidence. The attached scripts were not executed.
- Inspected the local no-commit/no-remote Git state, local instruction files and
  actual remote branch/main/CI state. Preserved all previous source and data.
- New `steamos-ios` directory/Xcode project links only new host code and Apple
  frameworks. All 3,672 archive files are hashed, CRC-checked and mapped.
- New branch `codex/steamos-ios-fresh`, based on main
  `3aa9fdb4b72d7127c4fe9c077aaf613937da293f`; existing branches and PRs untouched.
- User explicitly approved this branch's GitHub upload/build/probe prerelease
  after automatic approval review initially rejected publication. Approval is
  now present; do not ask for routine build/upload approval again.
- First build exposed C/C++ linkage; fixed with extern-C declarations. Corrected
  build `0e690ba47110ddc81aec63a6805ba9219812cf7e` passed source inventory,
  native Linux ASan/UBSan ABI smoke and actual Release ARM64 iOS Xcode build:
  https://github.com/aghjkshdsj/My-pc/actions/runs/36965566014
- Public prerelease `steamos-ios-host-probe-2`, build 4000001, independent public
  download verified size, checksum, full ZIP CRC, Mach-O iOS/ARM64, separate
  bundle ID and source identity. IPA 44,321 bytes; SHA-256
  `8aa308d0517b0bca1d2e28580755a3019ef797967c36eb6db0731ac83cfec1cd`.
- Source archive 233,440 bytes; SHA-256
  `11df1fea2abc149ca51c57ac518990da873339808c2936bdc9d48bfc8462f0ea`.
  This contains the fresh source only. No third-party engine is linked in this IPA.
- Owner was given the IPA URL and asked to run Metal/storage, enable StikDebug
  on the separate app, run JIT and return its JSON. No result received yet.
- Linux initramfs generator/ABI gate and negative evidence tests are written.
  Hosted **kernel** execution still needs CI; native Linux smoke is not a kernel
  boot on an iPhone. QEMU iOS engine integration and game GPU transport are
  unfinished. Do not turn a successful host probe into a Linux claim.

Research receipts: Apple Hypervisor/Virtualization metadata is macOS-only.
Valve ARM stable/beta manifests reachable; stable version 1788652215, beta
1790904859 at retrieval. Rootfs/casync index still external/unresolved.
Standard Venus has Linux external-memory requirements; current UTM fork
virglrenderer `5d26f605f50f8e22002ec6db5fb775e1992d4e96` has Darwin shared-memory
emulation through VK_EXT_external_memory_host worth testing. It still comments
that queue-family transfer emulation is incomplete. Current UTM main
`7eadb056ae0f91d979059544d0ddcd2d5a40be92` pins QEMU 10.0.12-utm and Venus/
Neptune; older Graphics.md is stale. KosmicKrisp docs explicitly lack iOS support.

Next: hosted real-kernel gate, source-pinned minimal iOS QEMU engine integration,
fresh phone Linux receipt, Linux GL/Vulkan patterned shader/presentation checks
using the upstream Darwin bridge, then official SteamOS/ARM Steam/CEF/session
integration. Retain the component ledger and phone performance distinction.
No Steam startup or Hollow Knight FPS target is verified.
