import Foundation
import CryptoKit
import zlib

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
expect(found[0].id == "folder:Example Game", "folder identity must be relative to the canonical Games directory: \(found[0].id); file=\(found[0].executable?.path ?? "none"); root=\(games.resolvingSymlinksInPath().standardizedFileURL.path)")
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
let withImportedEXE = try GameFiles.discover(in: games)
expect(withImportedEXE.count == 2, "EXE import discovery: \(withImportedEXE.map(\.id))")
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
// Profiles written by older builds must remain readable after Steam routing is added.
var legacyProfile = try JSONSerialization.jsonObject(with: JSONEncoder().encode(profile)) as! [String: Any]
legacyProfile.removeValue(forKey: "launchThroughSteam")
expect(try JSONDecoder().decode(GameProfile.self, from: JSONSerialization.data(withJSONObject: legacyProfile)).launchThroughSteam == nil, "legacy profile must use automatic routing")
profile.launchThroughSteam = false
expect(try JSONDecoder().decode(GameProfile.self, from: JSONEncoder().encode(profile)).launchThroughSteam == false, "direct-launch preference was lost")
expect(StartupStage.requested.percent == 1, "startup must begin at 1 percent")
expect(StartupStage.firstFrame.percent == 100, "first frame must be 100 percent")
expect(StartupStage.allCases.dropLast().allSatisfy { $0.percent < 100 }, "startup completed before first frame")
expect(zip(StartupStage.allCases, StartupStage.allCases.dropFirst()).allSatisfy { $0.percent < $1.percent }, "startup progress must be monotonic")
print("Startup milestone tests passed")

let indexURL = root.appendingPathComponent("index.json")
let index = try LibraryIndex(games: grouped, drive: drive)
try index.write(to: indexURL)
let restored = try LibraryIndex.read(indexURL, drive: drive)
expect(restored.games.map(\.id) == grouped.map(\.id), "saved index identity round trip")
expect(restored.games[0].candidates.map(\.lastPathComponent) == grouped[0].candidates.map(\.lastPathComponent), "saved EXE choices lost")
let newDrive = root.appendingPathComponent("new-container/drive_c")
try manager.createDirectory(at: newDrive, withIntermediateDirectories: true)
let relocated = try index.games(in: newDrive)
expect(relocated[0].executable!.path.hasPrefix(newDrive.path), "index retained the old iOS container path")
expect(!manager.fileExists(atPath: relocated[0].executable!.path), "index loading must not require a recursive rescan")
var hostileIndex = index
hostileIndex.entries[0].executable = "../escaped.exe"
rejects("cached traversal accepted") { _ = try hostileIndex.games(in: drive) }
hostileIndex = index
hostileIndex.entries.append(hostileIndex.entries[0])
rejects("duplicate cached identity accepted") { _ = try hostileIndex.games(in: drive) }
try Data("not json".utf8).write(to: indexURL)
rejects("corrupt index accepted") { _ = try LibraryIndex.read(indexURL, drive: drive) }
let emptyIndex = try LibraryIndex(games: [], drive: drive)
expect(try emptyIndex.games(in: drive).isEmpty, "empty library must remain a valid cached scan")
print("Persistent library index tests passed")

var account = try LocalAccountRecord.create(username: "Test User", password: "test-password-938")
let anotherAccount = try LocalAccountRecord.create(username: "Test User", password: "test-password-938")
expect(account.salt != anotherAccount.salt && account.verifier != anotherAccount.verifier, "accounts need independent random salts")
expect(try account.authenticate(username: "Test User", password: "test-password-938", remember: true), "correct local password rejected")
expect(account.remember, "remember sign-in not saved")
let attemptTime = Date()
for _ in 0..<5 { expect(try !account.authenticate(username: "Test User", password: "wrong-password", remember: true, now: attemptTime), "incorrect password accepted") }
expect(!account.remember, "failed login preserved remembered sign-in")
rejects("rate limit bypassed") { _ = try account.authenticate(username: "Test User", password: "test-password-938", remember: false, now: attemptTime) }
expect(try account.authenticate(username: "Test User", password: "test-password-938", remember: false, now: attemptTime.addingTimeInterval(31)), "rate limit did not expire")
expect(!account.remember && account.failures == 0, "successful login state incorrect")
let accountBytes = try JSONEncoder().encode(account)
expect(!String(decoding: accountBytes, as: UTF8.self).contains("test-password-938"), "password stored in plaintext")
var accountCopy = try JSONDecoder().decode(LocalAccountRecord.self, from: accountBytes)
expect(try accountCopy.authenticate(username: "Test User", password: "test-password-938", remember: false), "stored verifier round trip")
print("Local account verifier tests passed")

let wowOriginal = "[\(RuntimeRegistry.wowKey)] 42\n\"Installed\"=dword:00000000\n\n"
let wowActive = "[\(RuntimeRegistry.wowKey)]\n\"Installed\"=dword:00000001\n\n"
let dualOriginal = before + existing + wowOriginal + after
let dualActive = RuntimeRegistry.replacing(in: RuntimeRegistry.replacing(in: dualOriginal, with: replacement), with: wowActive, key: RuntimeRegistry.wowKey)
let journal = try JSONEncoder().encode([RuntimeRegistry.key: existing, RuntimeRegistry.wowKey: wowOriginal])
expect(try RuntimeRegistry.restore(in: dualActive, backup: journal) == dualOriginal, "dual-view registry restoration lost user state")
expect(try RuntimeRegistry.restore(in: activated, backup: JSONEncoder().encode(existing)) == original, "legacy registry journal migration")
rejects("registry journal accepted unrelated key") { _ = try RuntimeRegistry.restore(in: dualActive, backup: JSONEncoder().encode(["Other": "bad"])) }
expect(RuntimeRegistry.section(in: dualActive, key: RuntimeRegistry.wowKey) == wowActive, "WOW registry view missing")

let rankedGames = [LibraryGame.pc, .steam, LibraryGame(id: "game", title: "A Game", publisher: "", executable: nil, cover: nil, steamID: nil)]
let activity = ["pc": GameActivity(favorite: false, seconds: 500), "steam-client": GameActivity(favorite: true, seconds: 1), "game": GameActivity(favorite: false, seconds: 1000)]
expect(GameActivity.sorted(rankedGames, activity: activity).map(\.id) == ["steam-client", "game", "pc"], "favorite/playtime sorting")
expect(try JSONDecoder().decode([String: GameActivity].self, from: JSONEncoder().encode(activity)) == activity, "activity persistence")
expect(GameActivity.sorted(rankedGames, activity: [:]).first?.id == "pc", "new library default PC position")

let storeRoot = root.resolvingSymlinksInPath().appendingPathComponent("store")
try manager.createDirectory(at: storeRoot, withIntermediateDirectories: true)
for path in ["../escape", "/absolute", "C:\\outside", "a/../../escape", "a//b", "a/./b", "a\0b"] {
    rejects("unsafe store path: \(path)") { _ = try StoreFiles.destination(path, root: storeRoot) }
}
try manager.createSymbolicLink(at: storeRoot.appendingPathComponent("link"), withDestinationURL: root)
rejects("store symlink escape") { _ = try StoreFiles.destination("link/escape", root: storeRoot) }
expect(try StoreFiles.destination("directory\\game.exe", root: storeRoot).lastPathComponent == "game.exe", "Windows separators not normalized")

let fakeFile = "steam_win64.zip." + String(repeating: "a", count: 40)
let fakeHash = String(repeating: "b", count: 64)
let valveText = """
"win64" {
"version" "123"
"steam_win64" { "file" "\(fakeFile)" "size" "1234" "sha2" "\(fakeHash)" "steamchina" { "file" "ignored" } }
"bins_cef_win64" { "file" "bins_cef_win64.zip.\(String(repeating: "c", count: 40))" "size" "12345" "sha2" "\(fakeHash)" }
}
"kvsign2" "example"
"""
let valve = try ValveManifest(valveText)
expect(valve.packages.count == 2 && valve.version == "123", "Valve package nesting parsed incorrectly")
rejects("unsafe Valve package URL") { _ = try ValveManifest(valveText.replacingOccurrences(of: fakeFile, with: "../escape")) }
rejects("missing Valve package digest") { _ = try ValveManifest(valveText.replacingOccurrences(of: fakeHash, with: "bad")) }
rejects("duplicate Valve key") { _ = try ValveManifest(valveText.replacingOccurrences(of: "\"version\" \"123\"", with: "\"version\" \"123\" \"version\" \"456\"")) }

func storeZip(name: String, contents: Data, flags: UInt16 = 0, mode: UInt32 = 0, wrongCRC: Bool = false) -> Data {
    let nameBytes = Data(name.utf8)
    let crc = contents.withUnsafeBytes { UInt32(crc32(0, $0.bindMemory(to: UInt8.self).baseAddress, uInt(contents.count))) }
    var result = Data()
    func append(_ value: UInt32, width: Int = 4) { for index in 0..<width { result.append(UInt8((value >> (8 * index)) & 255)) } }
    append(0x04034b50); append(20, width: 2); append(UInt32(flags), width: 2); append(0, width: 2)
    append(0); append(crc); append(UInt32(contents.count)); append(UInt32(contents.count))
    append(UInt32(nameBytes.count), width: 2); append(0, width: 2)
    result.append(nameBytes); result.append(contents)
    let directoryStart = result.count
    append(0x02014b50); append(0x0314, width: 2); append(20, width: 2); append(UInt32(flags), width: 2); append(0, width: 2)
    append(0); append(wrongCRC ? crc ^ 1 : crc); append(UInt32(contents.count)); append(UInt32(contents.count))
    append(UInt32(nameBytes.count), width: 2); append(0, width: 2); append(0, width: 2)
    append(0, width: 2); append(0, width: 2); append(mode << 16); append(0)
    result.append(nameBytes)
    let directoryLength = result.count - directoryStart
    append(0x06054b50); append(0, width: 2); append(0, width: 2); append(1, width: 2); append(1, width: 2)
    append(UInt32(directoryLength)); append(UInt32(directoryStart)); append(0, width: 2)
    return result
}
let archive = root.appendingPathComponent("store.zip")
try storeZip(name: "folder/test.txt", contents: Data("verified".utf8)).write(to: archive)
try StoreZIP.extract(archive, to: storeRoot)
expect(try String(contentsOf: storeRoot.appendingPathComponent("folder/test.txt"), encoding: .utf8) == "verified", "ZIP extraction failed")
for (name, flags, mode, badCRC) in [("../escape", UInt16(0), UInt32(0), false), ("secret", 1, 0, false), ("symlink", 0, 0xa1ff, false), ("bad-crc", 0, 0, true)] {
    try storeZip(name: name, contents: Data("bad".utf8), flags: flags, mode: mode, wrongCRC: badCRC).write(to: archive)
    rejects("unsafe ZIP accepted \(name)") { try StoreZIP.extract(archive, to: storeRoot) }
}
expect(!manager.fileExists(atPath: storeRoot.appendingPathComponent("bad-crc").path), "bad checksum file published")
try Data([0, 1, 2]).write(to: archive)
rejects("truncated ZIP accepted") { try StoreZIP.extract(archive, to: storeRoot) }

let message = Data("GOG chunk verification".utf8)
var compressed = Data(count: Int(compressBound(uLong(message.count))))
var compressedLength = uLongf(compressed.count)
let compressionResult = compressed.withUnsafeMutableBytes { destination in
    message.withUnsafeBytes { source in
        compress2(destination.bindMemory(to: UInt8.self).baseAddress, &compressedLength, source.bindMemory(to: UInt8.self).baseAddress, uLong(message.count), Z_DEFAULT_COMPRESSION)
    }
}
expect(compressionResult == Z_OK, "test compression failed")
compressed.count = Int(compressedLength)
let chunk = GOGChunk(compressedMd5: StoreFiles.hex(Insecure.MD5.hash(data: compressed)), md5: StoreFiles.hex(Insecure.MD5.hash(data: message)), size: message.count, compressedSize: compressed.count)
expect(try GOGContent.decodeChunk(compressed, chunk: chunk) == message, "GOG chunk verification/decompression failed")
rejects("decompression size limit bypassed") { _ = try StoreFiles.inflated(compressed, limit: 1) }
rejects("corrupt GOG chunk accepted") { _ = try GOGContent.decodeChunk(compressed + Data([1]), chunk: chunk) }
let chunkURL = try GOGContent.chunkURL(base: URL(string: "https://gog-cdn-fastly.gog.com/content-system/v2/store?__token__=test")!, hash: chunk.compressedMd5)
expect(chunkURL.query == "__token__=test" && chunkURL.path.hasSuffix(chunk.compressedMd5), "GOG signed query was broken when appending chunk")
rejects("invalid GOG content hash") { _ = try GOGContent.hashPath("../secret") }
let chunkObject: [String: Any] = ["compressedMd5": chunk.compressedMd5, "md5": chunk.md5, "size": chunk.size, "compressedSize": compressed.count]
let depot: [String: Any] = ["depot": ["items": [["type": "DepotFile", "path": "Game\\Game.exe", "chunks": [chunkObject]]]]]
expect(try GOGContent.files(depot, product: "123", root: storeRoot).first?.path == "Game/Game.exe", "GOG manifest path conversion")
rejects("GOG depot link accepted") { _ = try GOGContent.files(["items": [["type": "DepotLink", "path": "outside"]]], product: "123", root: storeRoot) }
rejects("GOG depot traversal accepted") { _ = try GOGContent.files(["items": [["type": "DepotFile", "path": "../outside", "chunks": [chunkObject]]]], product: "123", root: storeRoot) }
if let archivePath = ProcessInfo.processInfo.environment["STEAM_SMOKE_ARCHIVE"] {
    try StoreZIP.extract(URL(fileURLWithPath: archivePath), to: storeRoot)
    expect(try GameFiles.gameExecutableMachine(storeRoot.appendingPathComponent("steam.exe")) == 0x8664, "official Steam bootstrap is not x86-64")
    print("Official Valve bootstrap extraction and 64-bit PE verification passed")
}
print("Store integrity/path safety, runtime migration, and library ranking tests passed")

expect(try GOGContent.authorizationCode(URL(string: "https://embed.gog.com/on_login_success?state=expected&code=authorized")!, state: "expected") == "authorized", "valid GOG OAuth callback rejected")
for callback in ["https://embed.gog.com/on_login_success?state=wrong&code=bad", "https://example.com/on_login_success?state=expected&code=bad", "https://embed.gog.com/on_login_success?state=expected&state=wrong&code=bad", "https://embed.gog.com/on_login_success?state=expected&code=first&code=second"] {
    rejects("invalid GOG OAuth callback accepted") { _ = try GOGContent.authorizationCode(URL(string: callback)!, state: "expected") }
}
expect(try LibraryIndex(games: [.pc, .steam], drive: drive).entries.isEmpty, "desktop entries must not be stored as scanned games")
if let manifestPath = ProcessInfo.processInfo.environment["STEAM_SMOKE_MANIFEST"] {
    let current = try ValveManifest(String(contentsOfFile: manifestPath, encoding: .utf8))
    print("Current official Steam win64 manifest parsed: \(current.packages.count) packages, version \(current.version)")
}
print("GOG OAuth callback safety tests passed")

func steamAppManifest(id: String = "480", directory: String = "Space Game", flags: String = "4") -> String {
    "\"AppState\" { \"appid\" \"\(id)\" \"name\" \"Space Game\" \"installdir\" \"\(directory)\" \"StateFlags\" \"\(flags)\" }"
}
let steamApp = try SteamInstalledApp(manifest: steamAppManifest(), fileName: "appmanifest_480.acf")
expect(steamApp.id == "480" && steamApp.directory == "Space Game", "installed Steam app parsing")
for id in ["0", "-1", "0480", "4294967296", "480 & whoami", "480\r\n", "４８０"] {
    expect(!SteamInstalledApp.validID(id), "unsafe/noncanonical Steam ID accepted")
    rejects("unsafe app launch accepted") { _ = try SteamLaunchPlan(width: 960, height: 540, appID: id) }
}
rejects("mismatched appmanifest filename") { _ = try SteamInstalledApp(manifest: steamAppManifest(), fileName: "appmanifest_481.acf") }
for folder in ["..", "../escape", "C:/outside", "a/b", ""] {
    rejects("unsafe Steam folder") { _ = try SteamInstalledApp(manifest: steamAppManifest(directory: folder), fileName: "appmanifest_480.acf") }
}
rejects("incomplete download accepted") { _ = try SteamInstalledApp(manifest: steamAppManifest(flags: "1024"), fileName: "appmanifest_480.acf") }
rejects("duplicate app ID accepted") { _ = try SteamInstalledApp(manifest: steamAppManifest().replacingOccurrences(of: "\"appid\" \"480\"", with: "\"appid\" \"480\" \"appid\" \"481\""), fileName: "appmanifest_480.acf") }
rejects("oversized appmanifest accepted") { _ = try SteamInstalledApp(manifest: String(repeating: " ", count: 1_048_577), fileName: "appmanifest_480.acf") }
let standardSteam = try SteamLaunchPlan(width: 960, height: 540)
expect(standardSteam.environment["MADEIRA_JITLESS"] == "1", "compatibility must remain default")
expect(standardSteam.environment["MADEIRA_USE_ARM64EC"] == "0" && standardSteam.environment["MADEIRA_DESKTOP"] == "1", "Steam must bootstrap native desktop before x64 children")
expect(standardSteam.environment["MADEIRA_ARGS"] == "/desktop=shell,960x540 cmd /c C:\\steam-launch.bat", "wrong desktop command")
expect(!standardSteam.batch.contains("-gamepadui") && !standardSteam.batch.contains("-console"), "default should not open extra UI")
expect(!standardSteam.batch.replacingOccurrences(of: "\r\n", with: "").contains("\n"), "batch must use CRLF")
let fastSteam = try SteamLaunchPlan(width: 1280, height: 720, interface: .bigPicture, webEngine: .jit, appID: "480")
expect(fastSteam.environment["MADEIRA_JITLESS"] == "0" && fastSteam.batch.contains("-gamepadui") && fastSteam.batch.contains("-applaunch 480"), "Steam selections not applied")
rejects("invalid screen size") { _ = try SteamLaunchPlan(width: -1, height: 540) }
expect(try SteamLaunchPlan.route(app: steamApp, preference: nil, arguments: "") == "480", "automatic Steam routing")
expect(try SteamLaunchPlan.route(app: steamApp, preference: false, arguments: "-example") == nil, "direct mode must remain available")
expect(try SteamLaunchPlan.route(app: nil, preference: nil, arguments: "") == nil, "imported game without manifest should launch directly")
rejects("forced Steam without manifest") { _ = try SteamLaunchPlan.route(app: nil, preference: true, arguments: "") }
rejects("custom shell arguments forwarded to batch") { _ = try SteamLaunchPlan.route(app: steamApp, preference: true, arguments: "& calc") }

let steamRoot = drive.appendingPathComponent("Steam", isDirectory: true)
let steamApps = steamRoot.appendingPathComponent("steamapps", isDirectory: true)
let steamGameRoot = steamApps.appendingPathComponent("common/Space Game", isDirectory: true)
try manager.createDirectory(at: steamGameRoot, withIntermediateDirectories: true)
let steamGameExe = steamGameRoot.appendingPathComponent("game.exe")
try executable(0x8664, at: steamGameExe)
let acf = steamApps.appendingPathComponent("appmanifest_480.acf")
try steamAppManifest().write(to: acf, atomically: true, encoding: .utf8)
let steamCatalog = try SteamLibraryCatalog(steamDirectory: steamRoot)
expect(steamCatalog.app(containing: steamGameExe)?.id == "480", "Steam game executable not associated with manifest")
expect(steamCatalog.app(containing: steamGameRoot)?.id == "480", "Steam folder metadata not associated")
expect(steamCatalog.app(containing: exe) == nil, "unrelated imported game matched Steam manifest")
let unrelated = steamApps.appendingPathComponent("appmanifest_482.acf")
try Data("damaged".utf8).write(to: unrelated)
expect(try SteamLibraryCatalog(steamDirectory: steamRoot).app(containing: steamGameExe)?.id == "480", "unrelated damaged manifest blocked valid game")
let duplicate = steamApps.appendingPathComponent("appmanifest_481.acf")
try steamAppManifest(id: "481", directory: "space game").write(to: duplicate, atomically: true, encoding: .utf8)
expect(try SteamLibraryCatalog(steamDirectory: steamRoot).app(containing: steamGameExe) == nil, "ambiguous installation must not launch an arbitrary Steam ID")
try manager.removeItem(at: duplicate)
try manager.removeItem(at: acf)
let outsideManifest = root.appendingPathComponent("outside.acf")
try steamAppManifest().write(to: outsideManifest, atomically: true, encoding: .utf8)
try manager.createSymbolicLink(at: acf, withDestinationURL: outsideManifest)
expect(try SteamLibraryCatalog(steamDirectory: steamRoot).app(containing: steamGameExe) == nil, "symlink manifest was followed")
print("Steam routing, profile migration, appmanifest validation, and launch-plan tests passed")

let clientDrive = root.appendingPathComponent("client-drive", isDirectory: true)
try manager.createDirectory(at: clientDrive, withIntermediateDirectories: true)
expect(SteamClientInstallation.findAll(in: clientDrive).isEmpty, "empty prefix reports Steam installed")
expect(SteamClientInstallation.libraryApps(for: nil).map(\.id) == ["pc", "steam-client"], "Steam must appear even before install or game scanning")
expect(!manager.fileExists(atPath: clientDrive.appendingPathComponent("Steam").path), "Steam detection must not create folders")
let managedClient = clientDrive.appendingPathComponent("Steam", isDirectory: true)
try manager.createDirectory(at: managedClient, withIntermediateDirectories: true)
try executable(0x8664, at: managedClient.appendingPathComponent("SteamSetup.exe"))
expect(SteamClientInstallation.findAll(in: clientDrive).isEmpty, "installer incorrectly treated as installed Steam")
try executable(0x8664, at: managedClient.appendingPathComponent("steam.exe"))
expect(SteamClientInstallation.findAll(in: clientDrive).isEmpty, "incomplete client without Steam DLL accepted")
try executable(0x8664, at: managedClient.appendingPathComponent("steamclient64.dll"))
let installedClient = SteamClientInstallation.findAll(in: clientDrive).first!
expect(installedClient.windowsDirectory == "C:\\Steam", "in-app Steam installer location not detected")
let installedApps = SteamClientInstallation.libraryApps(for: installedClient)
expect(installedApps.count == 2 && installedApps[1].id == "steam-client" && installedApps[1].executable?.lastPathComponent == "steam.exe", "installed Steam must replace its fixed launcher entry")
expect(installedApps[1].isDesktop, "Steam launcher must not require game EXE selection")
let emptyGameIndex = try LibraryIndex(games: [], drive: clientDrive)
expect(try emptyGameIndex.games(in: clientDrive).isEmpty, "empty game index fixture")
expect(SteamClientInstallation.libraryApps(for: installedClient)[1].title == "Steam", "Steam should be independent of a saved game index")
expect(try LibraryIndex(games: installedApps, drive: clientDrive).entries.isEmpty, "system app cards must not become cached game entries")
let installMarker = managedClient.appendingPathComponent(".somethingpc-installing")
try Data().write(to: installMarker)
expect(SteamClientInstallation.findAll(in: clientDrive).isEmpty, "interrupted Steam installation must not be launched")
try manager.removeItem(at: installMarker)
try executable(0x014c, at: managedClient.appendingPathComponent("steam.exe"))
expect(SteamClientInstallation.findAll(in: clientDrive).isEmpty, "unsupported 32-bit Steam accepted")
try executable(0x8664, at: managedClient.appendingPathComponent("steam.exe"))

for relative in SteamClientInstallation.relativeDirectories.dropFirst() {
    let folder = clientDrive.appendingPathComponent(relative, isDirectory: true)
    try manager.createDirectory(at: folder, withIntermediateDirectories: true)
    try executable(0x8664, at: folder.appendingPathComponent("steam.exe"))
    try executable(0x8664, at: folder.appendingPathComponent("steamclient64.dll"))
    let client = SteamClientInstallation.findAll(in: clientDrive).first { $0.directory == folder }!
    let plan = try SteamLaunchPlan(width: 960, height: 540, windowsDirectory: client.windowsDirectory)
    expect(plan.batch.contains("cd /d \"\(client.windowsDirectory)\"") && plan.batch.contains("\"\(client.windowsDirectory)\\steam.exe\""), "Steam must launch from its detected location")
}
expect(SteamClientInstallation.findAll(in: clientDrive).count == 3, "standard Steam locations not all detected")
for badDirectory in ["C:\\Steam\" & calc & \"", "C:\\Steam\ncalc", "C:\\%USERNAME%\\Steam", "Z:\\Steam"] {
    rejects("unsafe Steam command path") { _ = try SteamLaunchPlan(width: 960, height: 540, windowsDirectory: badDirectory) }
}
let alternateClient = clientDrive.appendingPathComponent("Program Files (x86)/Steam", isDirectory: true)
let alternateApps = alternateClient.appendingPathComponent("steamapps", isDirectory: true)
let alternateGame = alternateApps.appendingPathComponent("common/Space Game", isDirectory: true)
try manager.createDirectory(at: alternateGame, withIntermediateDirectories: true)
try executable(0x8664, at: alternateGame.appendingPathComponent("game.exe"))
try steamAppManifest().write(to: alternateApps.appendingPathComponent("appmanifest_480.acf"), atomically: true, encoding: .utf8)
let alternateGames = try SteamLibraryCatalog.discoverGames(in: alternateClient, drive: clientDrive)
expect(alternateGames.count == 1 && alternateGames[0].steamID == "480" && alternateGames[0].title == "Space Game", "games outside C:\\Games and C:\\Steam missing from Steam discovery")
expect(alternateGames[0].id.hasPrefix("steam:Program Files (x86)/Steam:"), "alternate Steam install has colliding IDs")
try manager.removeItem(at: acf)
try steamAppManifest().write(to: acf, atomically: true, encoding: .utf8)
let managedGames = try SteamLibraryCatalog.discoverGames(in: steamRoot, drive: drive)
expect(managedGames[0].id == "steam:folder:Space Game", "existing Steam game ID changed")

let linkedDrive = root.appendingPathComponent("linked-client-drive", isDirectory: true)
try manager.createDirectory(at: linkedDrive, withIntermediateDirectories: true)
try manager.createSymbolicLink(at: linkedDrive.appendingPathComponent("Steam"), withDestinationURL: managedClient)
expect(SteamClientInstallation.findAll(in: linkedDrive).isEmpty, "Steam client symlink escaped the prefix")
try manager.removeItem(at: managedClient.appendingPathComponent("steamclient64.dll"))
try manager.createSymbolicLink(at: managedClient.appendingPathComponent("steamclient64.dll"), withDestinationURL: alternateClient.appendingPathComponent("steamclient64.dll"))
expect(!SteamClientInstallation.findAll(in: clientDrive).contains { $0.directory == managedClient }, "linked Steam DLL accepted")
print("Steam fixed-library-entry, installation-detection, alternate-location and game-discovery tests passed")
