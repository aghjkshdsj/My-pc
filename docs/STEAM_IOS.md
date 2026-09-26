# Full Steam on iPhone

This integration uses the Windows 64-bit Steam client on My-pc's existing
Wine ARM64EC / FEX / DXMT stack. It does not convert Android executables to
iOS or use an Android Linux container.

## Use

1. In Settings → Steam & GOG, download/install the official Steam client.
   Installation requires Windows to be stopped, roughly 2 GB free, and the
   app to remain open. Existing steamapps, userdata, and config are preserved.
2. Keep Standard Steam and Compatibility selected initially. Enable JIT with
   the existing StikDebug setup. Debugger detection is only a preflight check;
   executable-memory allocation is checked during runtime startup.
3. Return to Library and tap Steam. Sign in, complete Steam Guard, and use
   Steam's store/library/download UI. No native account token importer is used.
4. Install into the default C:\Steam\steamapps\common location. Refresh Library
   after installation. Complete local appmanifest files supply game names and
   app IDs, even when the game does not ship a steam_appid.txt file.
5. Restart the app before starting another session. A game with a matching
   manifest launches through Steam using -applaunch, letting Steam select the
   configured launcher and handle its account session. Long-press a game → Game
   Settings → Launch using can force Steam or Direct EXE. Automatic preserves
   direct launches for imported games without a complete matching manifest.

For Steam launches, put additional arguments in Steam → Properties → Launch
Options. App-level EXE arguments are rejected with an explanation, rather than
inserted into a batch file. Direct EXE mode still supports those arguments.
Manually selecting an EXE does not override Steam's launcher in Steam mode.
Additional Steam library locations are not indexed by this integration.

## JIT and performance

- FEX CPU JIT is required for both Steam web-engine modes. The existing debugger
  allocation, dual-mapped executable pool, Wine child-process bridge, and Metal
  graphics path remain in use.
- Compatibility sets MADEIRA_JITLESS=1 for **V8 JavaScript only**. It does not
  disable FEX CPU JIT. Existing iPhone research documented hangs with V8 JIT;
  see STEAM_CEF_HANDOFF.md and build/ntdll-unix/process_ios.c.
- Web UI JIT sets MADEIRA_JITLESS=0 as an explicit experiment. It can improve
  JavaScript execution speed, but may hang/crash on this runtime. There is no
  automatic fallback after a native process fault. Restart and choose
  Compatibility to recover.
- Standard Steam avoids Big Picture's additional UI workload. Start at 960×540
  with a 60 FPS cap. Big Picture is available as an experimental option. No
  frame-rate or memory improvement has been measured for this change.
- Keep the existing default executable-pool configuration for Steam. Shrinking
  the debug pool or increasing it blindly can cause exhaustion or iOS termination.

## Source assessment

Reviewed aghjkshdsj/winlator-contents at
0d94db5ffe72a47f7d16f220714111d79ecc63e6. Its contents.json contains Android/Linux
component downloads. Its SteamLite agent is a separate headless Windows program
which needs a Steam token supplied by a separate authentication implementation
and matched Valve DLLs. It does not provide the full Steam login/store/download
interface requested here. No SteamLite source or Android packages are bundled.

My-pc's source base for this work is
3aa9fdb4b72d7127c4fe9c077aaf613937da293f. That base already installed the official
Steam client and had an experimental Steam tile. This change adds launch choices,
explicit JIT UI, local appmanifest discovery, and Steam-mediated game launches.

## Validation and limits

The Steam iOS integration checks workflow runs the existing Swift core suite plus
manifest, routing, batch-input, preference-migration, and symlink tests; the
existing debugger-script tests; and a complete iPhone Swift typecheck.

Those checks do not execute Steam, FEX, or a game on an iPhone. Steam login, Steam
Guard, downloads, client updates, CEF rendering, game DRM, anti-cheat, and frame
rates must be tested on a signed device build. The existing documented Wine/CEF
bugs are not claimed fixed. A rendered desktop also does not prove Steam login
or gameplay succeeded.

Device acceptance: install/repair; enable JIT; open Standard Steam; authenticate
with Steam Guard; download an owned 64-bit game; refresh Library; relaunch it
through Steam after an app restart; compare frame time, memory, and thermals with
Direct EXE where the game supports it. Test Big Picture/V8 JIT separately, and
record the iPhone model, iOS version, Steam version, game, and settings.
