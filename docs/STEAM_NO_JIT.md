# JIT-free iPhone build

This is a separate development track on `codex/steam-arm-interpreter`, stacked
on the ARM Linux port. It is not an App Store submission or a claim of approval.

## Implementation

- Build QEMU 10.0.12-utm with `--enable-tcg-threaded-interpreter` (TCTI),
  the ARM64 backend used by the pinned UTM `ios-tci` configuration. Dispatch
  code is compiled into the signed framework; guest code becomes interpreted
  data. Guest-side JavaScript JIT does not grant executable memory on iOS.
- Build iOS and macOS independently from the same pinned sources. Verify the
  interpreter configuration, disabled HVF, non-executable translation storage
  and framework checksum. Keep caches and artifacts separate from TCG JIT.
- Build a separate `MyPCInterpreter` iPhone app with an explicit source list,
  empty entitlements and a Linux-only bridge header. Wine, FEX, StikDebug,
  debugger attachment, JIT traps and the JIT JavaScript are excluded. The
  shared Swift sources select interpreter behavior at compile time.
- Keep Steam permanently visible in **Library → Apps**, independent of the
  games folder. Setup, persistent Linux storage, display and input use the
  ARM Linux port. The interpreter uses two virtual CPUs, 2 GiB guest RAM,
  a 128 MiB translation cache and software graphics.

## Verification and remaining work

1. Compile the shared launch tests in both modes and type-check the separate
   iPhone app. Audit the produced app for platform, unwanted runtime code,
   private framework dependencies and JIT-related entitlements.
2. Compile both interpreter frameworks. The CI host has a hardened ad-hoc
   signature and no JIT/debugger entitlements, but the hosted Mac allowed a
   `MAP_JIT` allocation despite that configuration. Do not claim its OS denies
   JIT. A CI-only allocation policy now intercepts QEMU's mmap/mprotect and VM
   protection APIs, denying MAP_JIT, anonymous executable allocations and
   executable promotions while allowing signed file-backed frameworks. Negative
   controls verify the denial in both an executable and a dlopened library.
   Linux boot, network, persistence, display, input and shutdown must then pass
   with zero prohibited allocation attempts. The policy library and probe are
   never bundled in the iPhone app. Disabling library validation is only for
   ad-hoc host CI frameworks; it is absent from the iPhone app.
3. Produce **MyPC-SteamARM64-NoJIT.ipa** as an unsigned development artifact
   only after those checks pass. The current workflow does not publish an
   App Store release. Full Steam startup under the interpreter and physical
   iPhone execution still need their own tests; a TCG JIT pass is not a TCTI pass.
4. Measure startup, memory pressure, battery use, login and small downloads on
   the iPhone 15 Pro Max. Expect substantial interpreter overhead. GPU, audio
   and games remain separate milestones. No usable gaming-performance promise
   is made for this build.
5. Before submission, complete app identity/icons, privacy disclosures,
   licensing and content permissions, supported-content indexing, age controls,
   purchasing behavior and Apple's review requirements. The Steam store and
   embedded CEF need review; removing JIT alone does not establish eligibility.

The iPhone build can be signed without `allow-jit` or `get-task-allow`. The
unsigned development IPA still needs signing to install. Testing on a hardened
Mac under the explicit CI allocation policy is evidence about the interpreter's
allocation behavior, not a replacement for iOS sandbox testing or App Review.

Build: `.github/workflows/steam-arm-interpreter.yml`. The next build uses the
checksummed guest from run `36586450467`, commit
`ccab0ec62a875a80fa16570d0dcf88442c109194`. This adds the missing `lsof`
dependency used by Steam to identify its loopback helper connections. The Apple
guest's previous run recorded 223 missing-lsof errors and 65 rejected local
connections. The image must exist with the pinned commit and valid checksums
before the interpreter boot/IPA jobs proceed. Full interpreter Steam startup
remains unverified. No Valve binaries are bundled.

The independent `.github/workflows/steam-interpreter-client.yml` uses the
verified TCTI framework from run `36586713923` and the same corrected guest.
It requires the full stable Steam login interface under the CI allocation
policy, with no account credentials or input. The native Linux and TCG JIT
passes cannot satisfy this gate. Its current first-install/CEF budgets are
30/10 minutes, with a 45-minute host startup limit; a timeout is a failed test
rather than a performance claim.

## Build evidence

Run `36506821950` at `bd1d30249f57322b79d7ee976066f33ce9935dc4` passed
launch validation in both compile modes and type-checked the separate iPhone
app. Both interpreter frameworks subsequently compiled successfully and QEMU's
configure summary selected TCTI. The post-build check failed because Meson's
boolean configuration uses a valueless `#define`, while the check required a
literal `1`. The check now accepts both valid enabled forms, with regression
tests that reject disabled, absent or conflicting interpreter/HVF settings.
Corrected run `36585373555` passed both framework builds and configuration
verification. Run `36586713923` reused those checked frameworks successfully
with the corrected guest. Both stopped before Linux boot because the hosted
Mac permitted MAP_JIT in the original OS-permission negative control. The
replacement policy test subsequently passed as recorded below; neither of
those earlier runs produced a JIT-free IPA.

Independent Xcode run `36507301434` at
`63d85d83cd12ea57a755d7f940ba79ddfa6c79d1` compiled and linked the actual
ARM64 iPhone executable successfully. Its symbol audit found no references to
the excluded JIT, Wine or FEX app bridges. That build does not include a runtime
or prove Linux/Steam execution. The independent app-build workflow catches
project/linker issues without waiting for the emulator build.

Run `36621003476`, commit `186582c90d084467146a6c98a6159658e587bb59`,
passed the corrected negative controls, both interpreter framework checks,
two actual Linux boots and the X11 input test under the CI allocation policy.
Each guest run completed with `denied_requests=0`, networking, persistence,
display and clean shutdown. The iPhone app audit and real
`MyPC-SteamARM64-NoJIT.ipa` packaging also passed. This is an Actions development
artifact, not a published Steam-ready release.

The full Steam test in run `36621522724` at
`f8519c6ff4ac45d11f7568c9f0afe385e753629f` failed its 30-minute first-install
budget. Steam's updater completed its approximately 666 MB download and was
still extracting when the test ended; no CEF helper or login window had
appeared. This establishes a startup/performance failure under the present
test budget, not a successful Steam interpreter test. The failed guest log
artifact is `11060001906`. Do not use the separate JIT login pass to satisfy
this gate, or publish the interpreter IPA as Steam-ready on this evidence.

The updated UI build, `d37357e69a24f3725b1473b6daf8b6fa39e92174` in run
`36624226244`, passed both launch-policy tests, CPU/FPS accounting checks,
the iPhone source type-check, both runtime checks and the actual guest boot/input
gate. Independent run `36624226237` also compiled and linked the updated ARM64
iPhone app. It adds a full-screen session, visible direct-touch/trackpad cursor,
right-click, scrolling, mouse drag, zoom and an optional process CPU/app memory/
desktop frame-rate overlay. GPU is explicitly software and no utilization
percentage is fabricated. Device validation of the controls and a usable
interpreter Steam startup remain outstanding.

That run also completed IPA packaging successfully. Actions artifact
`MyPC-SteamARM64-NoJIT-unsigned` (`11060197456`) contains the real interpreter
IPA, checksum and corresponding sources. The artifact ZIP digest is not the
IPA's checksum; this remains a development artifact rather than a Steam-ready
release.

The installed-client diagnostic `36627131232` at
`af151ae1b34794e2bb89d93ceb5cf0327654365c` used a fresh, account-free test disk.
JIT finished installation and reached the full login-interface gate, then shut
down. Booting the same installed disk under guarded TCTI reached CEF startup,
but the Steam launcher exited before a usable login interface passed. This is
another failed interpreter client gate, not merely a slow cold extraction.
The final health report counted five webhelper processes and no Steam process.
The cause is still under investigation using fixed-label exit/signal/OOM and
loopback diagnostics. This test disk is never included in the app or release.

References: [pinned UTM build configuration](https://github.com/utmapp/UTM/blob/7eadb056ae0f91d979059544d0ddcd2d5a40be92/scripts/build_dependencies.sh),
[pinned QEMU interpreter options](https://github.com/utmapp/qemu/blob/v10.0.12-utm/meson_options.txt),
[Apple App Review Guidelines, sections 2.5 and 4.7](https://developer.apple.com/app-store/review/guidelines/).
