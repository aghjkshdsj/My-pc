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
2. Compile both interpreter frameworks. On macOS, sign the host with hardened
   runtime and no JIT/debugger entitlements. A separate negative-control program
   must show that `MAP_JIT` is denied. Under those same restrictions, require
   Linux boot, networking, persistence, display, keyboard/mouse and shutdown.
   Disabling library validation is only for ad-hoc host CI frameworks; it is
   absent from the iPhone app.
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
Mac is evidence about host execution permissions, not a replacement for iOS
sandbox testing or App Review.

Build: `.github/workflows/steam-arm-interpreter.yml`. The next build uses the
checksummed guest from run `36586450467`, commit
`ccab0ec62a875a80fa16570d0dcf88442c109194`. This adds the missing `lsof`
dependency used by Steam to identify its loopback helper connections. The Apple
guest's previous run recorded 223 missing-lsof errors and 65 rejected local
connections. The image must exist with the pinned commit and valid checksums
before the interpreter boot/IPA jobs proceed. Full interpreter Steam startup
remains unverified. No Valve binaries are bundled.

## Build evidence

Run `36506821950` at `bd1d30249f57322b79d7ee976066f33ce9935dc4` passed
launch validation in both compile modes and type-checked the separate iPhone
app. Both interpreter frameworks subsequently compiled successfully and QEMU's
configure summary selected TCTI. The post-build check failed because Meson's
boolean configuration uses a valueless `#define`, while the check required a
literal `1`. The check now accepts both valid enabled forms, with regression
tests that reject disabled, absent or conflicting interpreter/HVF settings.
The corrected check and actual boot tests still need a new Actions run.

Independent Xcode run `36507301434` at
`63d85d83cd12ea57a755d7f940ba79ddfa6c79d1` compiled and linked the actual
ARM64 iPhone executable successfully. Its symbol audit found no references to
the excluded JIT, Wine or FEX app bridges. That build does not include a runtime
or prove Linux/Steam execution. The independent app-build workflow catches
project/linker issues without waiting for the emulator build.

References: [pinned UTM build configuration](https://github.com/utmapp/UTM/blob/7eadb056ae0f91d979059544d0ddcd2d5a40be92/scripts/build_dependencies.sh),
[pinned QEMU interpreter options](https://github.com/utmapp/qemu/blob/v10.0.12-utm/meson_options.txt),
[Apple App Review Guidelines, sections 2.5 and 4.7](https://developer.apple.com/app-store/review/guidelines/).
