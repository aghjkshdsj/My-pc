# Something PC 0.5

## Saved library

`somethingpc-library-index.json` stores the last successful scan atomically with a schema version, timestamp, and C:-relative paths. App launch, returning from Settings, choosing an EXE, and hiding/restoring cards do not recursively scan. A first launch without an index scans once. Imports and explicit Refresh library rebuild it. Missing/moved files are caught at launch; externally changed folders require manual refresh. A corrupt index reports an error rather than silently scanning again or modifying games. Relative paths survive an iOS container move. Steam and GOG imported games use separate roots, `C:\Steam\steamapps\common` and `C:\GOG Games`, with namespaced identities.

## Local account

First launch asks you to create the local account (username prefilled as Dan) and enter your chosen password. No password/default verifier is shipped in source or the IPA. The salted PBKDF2-HMAC-SHA256 verifier (600,000 rounds), failed-attempt cooldown and optional remembered sign-in are stored together in iOS Keychain with WhenUnlockedThisDeviceOnly accessibility. Save credentials remembers the sign-in rather than storing the plaintext password. Settings can require a password at the next launch without disrupting a running game. This is a local launch gate, not game-file encryption or a server account; it has no online recovery. Changing signing identity can change Keychain access.

## Store integration boundary

GameNative uses JavaSteam/DepotDownloader plus Android services for Steam, and GOG OAuth, manifests, authenticated CDN chunks, decompression and integrity checks for GOG. These are not included in this Swift/iOS runtime. The Steam & GOG screen deliberately labels its current capabilities: official website sign-in in the system browser and import of complete already-installed Windows game folders. It does not claim website login connects a native downloader. Store passwords/cookies are not accessed by app code or included in diagnostic exports. Steam-client/DRM dependencies may prevent imported games from running, and 32-bit store installers are unsupported. Full owned-library synchronization, native downloading/installation, updates and cloud saves remain unimplemented; merely adding login buttons cannot supply them.

## ScarletSkips / debugger diagnosis

The supplied build-39 report stops at startup 43%, during the 896 MiB debugger allocation, before Wine or the Windows EXE executes. It does not demonstrate a VC++ exception. Unsupported QSetIgnoredExceptions/QPassSignals responses are best-effort capability probes with existing fallbacks, not sufficient proof of the cause. A separate concrete script defect was found: `_M` error replies such as `E35` were parsed as hexadecimal pointers (0xe35), and malformed replies could throw. The script now rejects errors/malformed/unaligned replies without preparing that address. Protocol tests cover error and success responses. Release CI verifies that the tested JS file is copied byte-for-byte into the IPA instead of falling back to a stale embedded copy. Durable before/after allocation checkpoints distinguish a returned failure from a process/debugger termination. This does not prove ScarletSkips compatibility or diagnose the final iOS termination; matching app/StikDebug OS crash reports may still be needed.

Discovery produces one card per immediate game folder under `C:\Games`, not one card per executable. Redistributable/support directories (including `_Redist`, `_CommonRedist`, and engine prerequisites) and .NET/VC++ installers are excluded. The shallowest eligible EXE is selected only when unique; otherwise tapping the card opens its executable picker. Long-press Game Settings changes that choice. Hide removes a card without deleting files; Restore Hidden Games reverses it. Keep each game in its own immediate folder. Unknown helpers can remain in the executable picker, but do not create extra cards within a game folder.

The regular session opens a loading screen and then a fullscreen rendering area, with a floating menu for Library, keyboard, Escape, and diagnostics. The percentage counts completed startup milestones (JIT, files, runtime, pool, server, process, first frame); it is not an elapsed-time estimate or a game's internal loading percentage. 100% requires a new Metal present or substantial visible GDI surface update. This can be a splash/launcher/error window, not necessarily gameplay. A stalled step stays put and offers diagnostic sharing and an explicit show-session override. Advanced Diagnostics & JIT retains the developer interface.

GameNative's supplied Android source informed folder-based identity, explicit EXE selection, folder imports, and categorized settings. This is an independent iOS implementation; Android Vulkan drivers and Linux containers are not interchangeable with the existing Wine/FEX/DXMT Metal backend. No broad compatibility or performance improvement is claimed. Pool startup failures now remain available for diagnosis rather than scheduling an automatic app exit.

The library scans `Documents/wine/drive_c/Games` for regular `.exe` files, case-insensitively. Candidates must have MZ/PE headers, an executable-image flag, and a PE32/PE32+ optional-header signature, and must not have the DLL flag. Installer/crash helper names and symbolic links are excluded. The same application validation runs on EXE import and game launch. Cards show the actual executable filename as well as the display title. `.bin`, `.dll`, `.dat`, `.pak`, and other supporting files never become game cards, even if their contents resemble a PE image. Import Game Folder still copies the complete folder because games need those supporting files. Custom EXE copies only the executable; adjacent game data must be supplied separately. Games are never downloaded or bundled.

Artwork is resolved from `cover.png`, `cover.jpg`, `folder.jpg`, `header.jpg`, or an EXE-named image next to the executable. A numeric `steam_appid.txt` identifies official Steam artwork without guessing game names. Optional `somethingpc-game.json` accepts string fields `title`, `publisher`, `cover` (local relative image path), and `steamAppID`. Long-press a card to choose artwork and save per-game settings. Generic art is used if no verified identity/cover exists.

The PC tile opens the Wine desktop. One session per app process is supported. Restart to switch games or runtime profiles; the library offers Resume session. Existing signing/JIT requirements remain. JIT requests time out after 90 seconds.

## Runtime

An ARM64 Windows CI runner installs Microsoft's signed redistributable, verifies the installed DLL signatures/PE architectures, and records hashes plus actual installed version fields. The iOS app verifies these again before activating DLL links and the ARM64 registry key. The previous key is journaled and restored at next startup without replacing unrelated registry data. The Wine process recreates its default DLL links on every fresh session before the optional ARM64 overlay. ARM64 files go to the ARM64 farm (and system32 only in native ARM64 sessions); x64/ARM64EC exception handlers remain intact. No installer executes on iOS. This is experimental compatibility support, not a claim that Mecha Chameleon or Scarlet Skips is tested or fixed.

## Unexpected termination

A durable foreground-session marker is checked before LogStore rotates. Startup context and the last 4 MiB of the previous log are archived; large logs also preserve the first 128 KiB. Five unexpected-close reports are retained. Structured diagnostics include build commit, effective settings/runtime manifest, selected EXE, discovered launcher candidates, controllers, startup milestones, and a bounded memory/thermal history. Available MetricKit diagnostics are retained locally, but delivery can be delayed or absent and may describe earlier sessions. Reports explicitly distinguish this from a complete native crash trace; iOS `.ips` or JetsamEvent reports may still be required. No Wine/FEX signal handlers are replaced.

Settings > Diagnostics & Sharing exports the current report. Close acknowledges the unexpected-close prompt without deleting its report; Share opens the system share sheet with no automatic upload. Foreground force-quit/OS termination can also trigger the prompt; background kills may not. Reports include private filenames and game output: review before sharing. Release CI preserves the matching iOS debug symbols separately for native crash analysis.

## Validation

`swiftc app/Madeira/GameLibraryCore.swift app/Madeira/LocalAccountCore.swift build/app-tests/main.swift -o /tmp/app-tests && /tmp/app-tests`

`node build/app-tests/jit-script.test.cjs`

CI tests PE validation, path containment, symlink rejection, discovery filtering, metadata, folder/EXE imports, profile round trips, and registry activation/restoration. Release CI builds the complete iOS app and downloads its published IPA to compare bytes and checksum. Real-device testing is still required for layout, controller behavior, JIT launch, and game/runtime compatibility. Back up app documents before installing.
