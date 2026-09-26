# Madeira

Run Windows PC games on a non-jailbroken iPhone.

Madeira combines [Wine](https://www.winehq.org/) (ARM64EC),
[FEX-Emu](https://github.com/FEX-Emu/FEX) for x86-64 → ARM64 translation, and
[DXMT](https://github.com/3Shain/DXMT) for D3D11 → Metal, running as a single
Mach process on iOS with wineserver as a thread rather than a separate process.

## Status

### Something PC 0.6

- Favorites (star button) sort before accumulated foreground session time. Library/settings/background time is excluded. Playtime checkpoints every 15 seconds; this is session time, not per-process Steam game telemetry.
- Settings → Steam & GOG downloads the official 64-bit Steam client directly from Valve and verifies manifest SHA-256 plus ZIP CRC/size/path checks. The Steam card opens the desktop, then Steam. Sign in and download owned games inside that client. This is experimental Wine/CEF compatibility, **not** native Steam library synchronization or a guarantee that Steam login works on every device.
- GOG uses official OAuth pages, device-only Keychain tokens, owned-library access and generation-2 depot downloads with compressed/uncompressed checksums. Installs to `C:\GOG Games`; cancelled downloads can reuse verified chunks. English and 64-bit/neutral depots are supported. Generation-1/offline installers, post-install scripts, prerequisite automation, cloud saves and game updates are not implemented. Existing game folders are never overwritten.
- Install with Windows stopped; keep the app open. Steam preserves existing `steamapps`, `userdata` and `config`. Refresh Library after installing games through the Windows Steam client.
- Bundled ARM64 VC++ registration now covers both native and WOW64 registry views; switching it off restores prior entries. This corrects a detection omission, **not** the separate ScarletSkips memory-write fault observed after its VC++ DLLs loaded.
- Shared reports now include bounded recent Unreal `Saved/Logs` and `Saved/Crashes/CrashContext.runtime-xml` content. Review for private information before sharing. No automatic upload.

Store protocol handling was informed by the user-supplied GameNative source; see `THIRD-PARTY-NOTICES.md`. Apple/iOS and Windows compatibility are different: installing a game does not establish that it can run.

Thumper and ULTRAKILL are playable. Marvel Cosmic Invasion has reached
gameplay, though a run has also ended in an unexplained termination and its
controls are not yet reliable. Others reach gameplay at low frame rates. This
is a research project, not a product: expect rough edges, per-title quirks and
breaking changes.

## Steam launch options

Settings → Steam & GOG now offers Standard Steam or experimental Big Picture,
an explicit StikDebug JIT action, and a separate experimental web-UI JIT option.
FEX CPU JIT remains required in both web modes. Local Steam appmanifests supply
installed game names/IDs; matching games launch through Steam by default, with
Automatic / Steam client / Direct EXE choices in Game Settings. This builds on
the existing official Valve installer; Android component archives are not used.
See [iPhone Steam setup and validation limits](docs/STEAM_IOS.md). These changes
do not establish successful iPhone login, game compatibility, or measured FPS.

## Requirements

- A non-jailbroken iPhone. Development has been on an A15 (iPhone 13 Pro).
- JIT, which on iOS requires a debugger to attach —
  [StikDebug](https://github.com/0-Blu/StikJIT) is what this project uses.
- An Apple ID for signing. A free account works; its provisioning profiles
  expire after 7 days, so the app must be rebuilt and reinstalled weekly. The
  app's container survives reinstall, so prefixes and saves are preserved.

Because JIT requires debugger attach, this app cannot be distributed through the
App Store. It is installed by sideloading.

## Building

The build is split across several chains — the unix-side Wine libraries, the
ARM64EC PE modules, FEX, DXMT and the iOS app itself. `build/*/build.sh` covers
the native pieces; the app is built with `xcodebuild`.

```sh
git clone --recurse-submodules <this repo>
```

Note that `FEX`, `wine` and `research/dxmt` are submodules pointing at forks
containing the iOS work; upstream clones will not build here.

## License

**GPL-3.0-or-later** — see [`LICENSE`](LICENSE). Derivatives that are
distributed must remain open source.

### Upstream licenses vs. this project's forks

Those are the licenses of the **upstream projects**: Wine and GnuTLS
LGPL-2.1-or-later, GMP and Nettle LGPL-3.0-or-later, FEX-Emu and DXMT MIT,
rpmalloc 0BSD. Their texts are in [`LICENSES/`](LICENSES), and upstream code
remains available under them **from upstream**.

**The forks used here are not licensed identically to their upstreams.** Each
carries its own `LICENSE-MADEIRA.md` saying exactly what applies:

| Fork | Terms |
|---|---|
| [`wine`](https://github.com/willfaust/wine) | relicensed to **GPL-3.0-or-later** under LGPL-2.1 §3 |
| [`FEX`](https://github.com/willfaust/FEX), [`dxmt`](https://github.com/willfaust/dxmt) | upstream MIT preserved; modifications **GPL-3.0-or-later** |
| [`rpmalloc`](https://github.com/willfaust/rpmalloc) | upstream 0BSD preserved; Will Faust's modifications **GPL-3.0-or-later** |

This is not retroactive: those forks were public beforehand, so anything
already obtained under a permissive license stays available under it.

[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) has the per-component
breakdown. Note in particular that the Microsoft Visual C++ runtime DLLs are
not distributed here and must be supplied yourself — see
[`tools/fetch-vcruntime.md`](tools/fetch-vcruntime.md).

## A note on upstream contributions

The forks here contain substantial AI-assisted work. FEX-Emu's contribution
policy states that AI must not be used to generate code for contributions to
that project, so **do not submit AI-generated changes from this fork upstream**.
The MIT license permits the fork itself; the policy governs contributions back.
Check each upstream's contribution policy before proposing changes to it.
