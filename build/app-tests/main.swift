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
expect(try String(contentsOf: storeRoot.appendingPathComponent("folder/test.txt")) == "verified", "ZIP extraction failed")
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
