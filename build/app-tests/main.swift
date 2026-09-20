import Foundation

func expect(_ condition: Bool, _ message: String) {
    guard condition else { fatalError(message) }
}

func rejects(_ message: String, _ action: () throws -> Void) {
    do { try action(); fatalError(message) } catch { }
}

let manager = FileManager.default
let root = manager.temporaryDirectory.appendingPathComponent("somethingpc-tests-" + UUID().uuidString, isDirectory: true)
try manager.createDirectory(at: root, withIntermediateDirectories: true)
defer { try? manager.removeItem(at: root) }
let drive = root.appendingPathComponent("drive_c", isDirectory: true)
let games = drive.appendingPathComponent("Games", isDirectory: true)
let game = games.appendingPathComponent("Example Game", isDirectory: true)
try manager.createDirectory(at: game, withIntermediateDirectories: true)

func executable(_ machine: UInt16, at url: URL) throws {
    var bytes = Data(repeating: 0, count: 512)
    bytes[0] = 0x4d; bytes[1] = 0x5a; bytes[60] = 64
    bytes[64] = 0x50; bytes[65] = 0x45
    bytes[68] = UInt8(machine & 255); bytes[69] = UInt8(machine >> 8)
    bytes[84] = 240; bytes[86] = 0x22
    bytes[88] = 0x0b; bytes[89] = 0x02
    try bytes.write(to: url)
}

let exe = game.appendingPathComponent("Example.exe")
try executable(0x8664, at: exe)
expect(try GameFiles.machine(exe) == 0x8664, "x64 machine detection")
let arm = root.appendingPathComponent("native.exe")
try executable(0xaa64, at: arm)
expect(try GameFiles.machine(arm) == 0xaa64, "ARM64 machine detection")
try executable(0xa64e, at: arm)
expect(try GameFiles.machine(arm) == 0xa64e, "ARM64X machine detection")
let bad = root.appendingPathComponent("bad.exe")
try Data("not an exe".utf8).write(to: bad)
rejects("invalid PE accepted") { _ = try GameFiles.machine(bad) }
let hostile = root.appendingPathComponent("hostile.exe")
var malformed = Data(repeating: 255, count: 64)
malformed[0] = 0x4d; malformed[1] = 0x5a
try malformed.write(to: hostile)
rejects("unbounded PE offset accepted") { _ = try GameFiles.machine(hostile) }
expect(try GameFiles.windowsPath(exe, drive: drive) == "C:\\Games\\Example Game\\Example.exe", "Windows path mapping")
rejects("outside drive accepted") { _ = try GameFiles.windowsPath(arm, drive: drive) }
expect(!GameFiles.isInside(root.appendingPathComponent("drive_c-other/Game.exe"), root: drive), "sibling prefix traversal")
try manager.createSymbolicLink(at: game.appendingPathComponent("escaped.exe"), withDestinationURL: arm)
expect(!GameFiles.isInside(game.appendingPathComponent("escaped.exe"), root: games), "symlink escape")
try executable(0x8664, at: game.appendingPathComponent("unins000.exe"))
try executable(0x8664, at: game.appendingPathComponent("CrashReportClient.exe"))
try Data().write(to: game.appendingPathComponent("cover.png"))
try Data("480\n".utf8).write(to: game.appendingPathComponent("steam_appid.txt"))
try Data("{\"title\":\"Example Title\",\"publisher\":\"Example Studio\"}".utf8).write(to: game.appendingPathComponent("somethingpc-game.json"))
let found = try GameFiles.discover(in: games)
expect(found.count == 1, "discovery included helper executables or symlinks")
expect(found[0].title == "Example Title" && found[0].publisher == "Example Studio", "local metadata")
expect(found[0].cover?.lastPathComponent == "cover.png" && found[0].steamID == "480", "cover metadata")
for name in ["assets.bin", "data.dll", "resources.dat", "level.pak", "Game.exe.bin", "Game.exe.txt", "shortcut.lnk"] {
    let candidate = game.appendingPathComponent(name)
    try executable(0x8664, at: candidate)
    rejects("non-EXE accepted: \(name)") { _ = try GameFiles.gameExecutableMachine(candidate) }
    rejects("non-EXE import accepted: \(name)") { try GameFiles.copyImport(candidate, to: games, folder: false) }
}
try Data("game data renamed as EXE".utf8).write(to: game.appendingPathComponent("renamed.bin.exe"))
let disguisedDLL = game.appendingPathComponent("library.exe")
try executable(0x8664, at: disguisedDLL)
var dllBytes = try Data(contentsOf: disguisedDLL)
dllBytes[87] = 0x20
try dllBytes.write(to: disguisedDLL)
rejects("DLL renamed EXE accepted") { _ = try GameFiles.gameExecutableMachine(disguisedDLL) }
let invalidImage = game.appendingPathComponent("object.exe")
try executable(0x8664, at: invalidImage)
var objectBytes = try Data(contentsOf: invalidImage)
objectBytes[86] = 0
try objectBytes.write(to: invalidImage)
rejects("non-executable PE accepted") { _ = try GameFiles.gameExecutableMachine(invalidImage) }
try manager.createDirectory(at: game.appendingPathComponent("folder.exe"), withIntermediateDirectories: true)
expect(try GameFiles.discover(in: games).map(\.id) == found.map(\.id), "non-EXE data, fake EXEs or DLLs became game cards")
let uppercase = game.appendingPathComponent("Uppercase.EXE")
try executable(0x8664, at: uppercase)
let ambiguous = try GameFiles.discover(in: games)
expect(ambiguous.count == 1 && ambiguous[0].candidates.count == 2, "one folder must produce one card with two EXE choices")
expect(ambiguous[0].executable == nil, "ambiguous main EXEs must require a selection")
try manager.removeItem(at: uppercase)
for folderName in ["_Redist", "_CommonRedist", "Engine/Extras/Redist", "Support/Installers"] {
    let folder = game.appendingPathComponent(folderName)
    try manager.createDirectory(at: folder, withIntermediateDirectories: true)
    try executable(0x8664, at: folder.appendingPathComponent("dotNetFx40_Full_setup.exe"))
    try executable(0x8664, at: folder.appendingPathComponent("UnusualHelper.exe"))
}
try executable(0x8664, at: game.appendingPathComponent("dotNetFx40_Full_setup.exe"))
try executable(0x8664, at: game.appendingPathComponent("UEPrereqSetup_x64.exe"))
let binaryFolder = game.appendingPathComponent("Binaries/Win64")
try manager.createDirectory(at: binaryFolder, withIntermediateDirectories: true)
try executable(0x8664, at: binaryFolder.appendingPathComponent("Example-Win64-Shipping.exe"))
let grouped = try GameFiles.discover(in: games)
expect(grouped.count == 1 && grouped[0].candidates.count == 2, "redistributables or helper folders leaked into game choices")
expect(grouped[0].executable?.resolvingSymlinksInPath().standardizedFileURL.path == exe.resolvingSymlinksInPath().standardizedFileURL.path,
    "top-level game launcher should take precedence over its shipping binary: \(grouped[0].executable?.path ?? "none") versus \(exe.path)")
expect(GameFiles.isSupportPath("Title/_Redist/dotNetFx40_Full_setup.exe"), "screenshot installer not filtered")
expect(!GameFiles.isSupportPath("Title/Binaries/Win64/Title-Win64-Shipping.exe"), "Unreal game binary incorrectly filtered")
let installerOnly = games.appendingPathComponent("Installer Only/_Redist")
try manager.createDirectory(at: installerOnly, withIntermediateDirectories: true)
try executable(0x8664, at: installerOnly.appendingPathComponent("UnusualHelper.exe"))
expect(try GameFiles.discover(in: games).count == 1, "installer-only folder became a game card")
try Data("../../evil".utf8).write(to: game.appendingPathComponent("steam_appid.txt"))
expect(try GameFiles.discover(in: games)[0].steamID == nil, "invalid Steam ID accepted")
try GameFiles.copyImport(arm, to: games, folder: false)
expect(try GameFiles.discover(in: games).count == 2, "EXE import discovery")
rejects("invalid imported EXE accepted") { try GameFiles.copyImport(bad, to: games, folder: false) }
rejects("recursive folder import accepted") { try GameFiles.copyImport(drive, to: games, folder: true) }
rejects("symlink-containing import accepted") { try GameFiles.copyImport(game, to: games, folder: true) }
let source = root.appendingPathComponent("Full Game")
try manager.createDirectory(at: source, withIntermediateDirectories: true)
try executable(0x8664, at: source.appendingPathComponent("Play.exe"))
try Data("game assets".utf8).write(to: source.appendingPathComponent("data.bin"))
try GameFiles.copyImport(source, to: games, folder: true)
let imported = try GameFiles.discover(in: games).first { $0.title == "Play" }!
expect(manager.fileExists(atPath: imported.executable!.deletingLastPathComponent().appendingPathComponent("data.bin").path), "folder assets lost")

let existing = "[\(RuntimeRegistry.key)] 123\n\"Installed\"=dword:00000000\n\n"
let replacement = "[\(RuntimeRegistry.key)]\n\"Installed\"=dword:00000001\n\n"
let before = "WINE REGISTRY Version 2\n\n[Other] 1\n\"Value\"=\"keep\"\n\n"
let after = "[Another] 2\n\"Value\"=\"also keep\"\n"
let original = before + existing + after
expect(RuntimeRegistry.section(in: original) == existing, "registry section extraction")
let activated = RuntimeRegistry.replacing(in: original, with: replacement)
expect(activated == before + replacement + after, "unrelated registry keys changed")
expect(RuntimeRegistry.replacing(in: activated, with: existing) == original, "registry rollback")
let last = before + String(existing.dropLast(2))
expect(RuntimeRegistry.section(in: last) == String(existing.dropLast(2)), "EOF section without newline")
expect(!RuntimeRegistry.replacing(in: last, with: "").contains(RuntimeRegistry.key), "EOF removal")
let absent = before + after
expect(RuntimeRegistry.section(in: absent).isEmpty, "absent key extraction")
expect(!RuntimeRegistry.replacing(in: RuntimeRegistry.replacing(in: absent, with: replacement), with: "").contains(RuntimeRegistry.key), "new key rollback")
var profile = GameProfile()
profile.customSettings = true; profile.visualCppARM64 = true; profile.resolution = "1280x720"
expect(try JSONDecoder().decode(GameProfile.self, from: JSONEncoder().encode(profile)) == profile, "profile round trip")
print("All Something PC library/runtime registry tests passed")
expect(StartupStage.requested.percent == 1, "startup must begin at 1 percent")
expect(StartupStage.firstFrame.percent == 100, "first frame must be 100 percent")
expect(StartupStage.allCases.dropLast().allSatisfy { $0.percent < 100 }, "startup completed before first frame")
expect(zip(StartupStage.allCases, StartupStage.allCases.dropFirst()).allSatisfy { $0.percent < $1.percent }, "startup progress must be monotonic")
print("Startup milestone tests passed")
