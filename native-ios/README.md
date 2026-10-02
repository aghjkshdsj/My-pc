# My-pc Native iOS Steam

This is the separate native version requested on October 1, 2026. It builds
the iOS Steam account, library and content-download frontend and runs Windows
games through native ARM64EC Wine, FEX and DXMT/Metal. Its app target contains
no QEMU, Linux guest, virgl, guest filesystem or VM startup.

**Launch Steam**, beside **Desktop**, opens the full **Windows x64 Steam client
inside Wine/FEX**, not the Linux ARM64 client from preview 33. The first launch
downloads Valve's current `steam_client_win64` distribution (about 340 MiB
compressed at implementation time), verifies every package size/SHA-256 and
ZIP CRC, and installs it as `C:\SteamDesktop` in one rename. Setup supports
cancellation and preserves existing conflicting files. Enable JIT first and
sign in in Steam's own window. Its CEF interface is experimental on iOS; phone
testing of login, rendering, updates and games remains required.

The desktop client is separate from the pinned native game-launch helper.
Its library configuration includes the existing native Windows download folder;
owner-added desktop library configuration is preserved after first setup.
The native account connection logs off before a desktop session. Client
discovery registry keys naming `SteamDesktop` are restored for the next native
game launch. No account token is written to the desktop launch command.
The app name is My-pc Native and its icon is the original blue PC icon from
preview 33. The Steam button uses Valve's Steam mark and the Desktop button's
Liquid Metal/system capsule style, including controller navigation.

The existing Steam ARM64 preview remains on `codex/steam-arm-metal`.
`com.aghjkshdsj.mypc.native` is a separate app identity: installing this preview
does not replace that app or migrate/delete its Linux disk, account or games.
Steam downloads in the new app select Windows depots for Wine; existing Linux
game downloads cannot simply be relabeled as Windows installations.

## Source and build

`source-lock.json` pins the complete Madeira source and each of its runtime
forks. `checkout-source.sh` checks out exactly those revisions under the ignored
`runtime/` directory. `prepare.py` applies the checked My-pc overlay. This is
an attributed port of the referenced native implementation, not a claim to have
rewritten Valve's proprietary client, Wine or FEX from scratch. The supplied
0.1.0 ZIP informed the architecture; the pinned public source contains later
account handoff and launch fixes.

`app-overlay.py` applies only Swift, Xcode project and asset changes after the
native compiler-input overlay. Native component caches depend on the pinned
runtime and C build inputs; app source is freshly compiled and typechecked.
`test-steam-desktop.py` compiles the actual Foundation manifest, ZIP, PE and
registry policy at `-O` against captured public metadata and hostile fixtures.

The source keeps its GPL-3.0-or-later / Madeira Converter Exception notices,
the Wine LGPL notices and other component notices. Release source archives
include the checked-out source, recursively checked-out runtime forks, the
overlay and the build scripts. Valve components are downloaded from Valve by
the app and verified; credentials and games are never bundled.

Run on a Mac with Xcode and the iOS SDK:

```sh
bash native-ios/checkout-source.sh
bash native-ios/build-component.sh fex
bash native-ios/build-component.sh wine
bash native-ios/build-component.sh dxmt
bash native-ios/build-component.sh dock
bash native-ios/package.sh
```

The workflow builds native iOS libraries from their locked source revisions.
Swift account, library and download code is compiled with `-O` and whole-module
optimization. The protocol tests exercise that Swift optimization under
AddressSanitizer. C/Objective-C app code retains the reference's Debug flags
because the reference reports guest crashes with its fully Release host;
FEX, Wine and DXMT libraries have their own optimized source builds. Device
testing of this combination remains required.
The upstream Windows DLL farms remain pinned source-repository inputs; their
provenance is recorded in the release. They are not silently substituted with
the older preview-33 runtime. JIT is needed when launching translated games,
but browsing and downloading in the native library do not start Wine or JIT.

## Performance acceptance

Opening the app must show the native library without starting Wine, FEX or a
Linux VM. The performance report records app-init-to-library time separately
from account refresh, download throughput, game launch and actual Metal
presents. It contains no account name, token, password, file path or game list.

The under-one-minute target requires an external cold-launch timing on the
owner's iPhone. A UI timer cannot measure pre-main loading or time before the
process starts. Game FPS must be measured in a named game at a stated resolution
after its game window appears; CI shader loops and Android reference numbers
are not evidence of iPhone game performance. Record thermal state and compare
the same game, scene and settings. The preview-33 reports were hot.

The owner's first game target is **Hollow Knight at 60–80 FPS**. Start with its
Windows depot at 1280×720 and record the actual resolution, scene, launch time
and thermal state. This is a measurement target, not a verified result. Use the
same save and route for comparisons, and record any game frame cap or VSync
setting separately from performance. JIT must be enabled for **My-pc Native**
before launching a game; check JIT and Memory+ readiness in the app's Settings.

The IPA verifier handles Xcode's Debug layout: it verifies the ARM64 iOS
launcher and the referenced `Madeira.debug.dylib` containing the actual app
code. It rejects macOS and simulator binaries, missing app code and VM payloads.

Valve authenticates the account, confirms licenses and prepares protected
executables. The Dock helper fails closed for unsupported client fingerprints
or rejected authentication/licenses. The app closes its Steam library connection
before the helper signs in, then resumes only after the game session ends.
These checks and waits remain part of a real game launch.

## Dokimon launch regression

The owner's build-3000008 log confirms that Steam accepted Dokimon Quest: II
(app 2019300), but Wine moved its 0xa88000-byte x64 executable away from
0x140000000 and terminated it with `STATUS_CONFLICTING_ADDRESSES` (`c0000018`)
before executing the game. Its PE characteristics are 0x23, including
`IMAGE_FILE_RELOCS_STRIPPED`; this executable cannot be relocated. The reserved
executable-window helper incorrectly treated every image below 64 MB as movable.

`wine-build-fixes.py` permits a non-builtin x64 main executable with that flag
to claim its preferred address even below the size floor. DLLs, relocatable
images, WoW64 windows and anonymous allocations retain the original policy.
The existing ownership, retirement, no-overwrite mapping and claim rollback
remain active. `test-fixed-image.py` compiles the actual patched policy and claim
functions under ASan/UBSan, exercising the reported executable size, exclusions,
address bounds, live-owner rejection and the exact retired-interval handoff.
Host VM operations are mocked; a successful phone launch is still required.

The same log also records access violations in a Steam helper during shutdown,
after the game's loader failure. Those are separate from the first failure and
remain under investigation; this placement fix does not claim to resolve them.
