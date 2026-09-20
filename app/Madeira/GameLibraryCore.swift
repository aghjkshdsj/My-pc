import Foundation

struct GameProfile: Codable, Equatable {
    var customSettings = false
    var visualCppARM64 = false
    var resolution = "960x540"
    var showFPS = true
    var presentationMode: Int32 = 1
    var keepAwake = true
    var controllerMode = "xinput"
    var deadZone = 0.15
    var mouseSpeed = 8.0
    var relativeMouse = false
    var pointerSensitivity = 2.0
    var mouseLookSensitivity = 2.0
    var diagnostics = false
    var arguments = ""
    var customCover: String?
}

struct LibraryGame: Identifiable, Equatable {
    let id: String
    let title: String
    let publisher: String
    let executable: URL?
    let cover: URL?
    let steamID: String?
    var candidates: [URL] = []
    var folder: URL?
    static let pc = LibraryGame(id: "pc", title: "PC", publisher: "Windows desktop", executable: nil, cover: nil, steamID: nil)
}

enum LibraryFailure: LocalizedError {
    case invalid(String)
    var errorDescription: String? {
        switch self { case .invalid(let message): return message }
    }
}

enum GameFiles {
    static func isSupportPath(_ relativePath: String) -> Bool {
        let parts = relativePath.lowercased().split(separator: "/").map(String.init)
        let folders: Set<String> = ["_redist", "_commonredist", "redist", "redistributables", "redistributable", "prerequisites", "prereqs", "__installer", "installers", "directx", "dotnet", "dotnetfx", "vcredist", "support", "extras"]
        if parts.dropLast().contains(where: folders.contains) { return true }
        let stem = URL(fileURLWithPath: parts.last ?? "").deletingPathExtension().lastPathComponent
        let helpers = ["unins", "uninstall", "setup", "install", "vc_redist", "vcredist", "dotnet", "ndp", "dxsetup", "directx", "ueprereq", "crashreport", "crashpad", "unitycrashhandler", "unitybugreport", "cefsubprocess", "unrealcefsubprocess", "bsppack", "dxwebsetup"]
        return helpers.contains(where: stem.hasPrefix) || stem.hasSuffix("_setup") || stem.hasSuffix("_installer")
    }

    static func isInside(_ file: URL, root: URL) -> Bool {
        let base = root.resolvingSymlinksInPath().standardizedFileURL.path
        let candidate = file.resolvingSymlinksInPath().standardizedFileURL.path
        return candidate.hasPrefix(base + "/")
    }

    private static func peHeader(_ url: URL) throws -> Data {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        let header = try handle.read(upToCount: 64) ?? Data()
        guard header.count == 64, header[0] == 0x4d, header[1] == 0x5a else {
            throw LibraryFailure.invalid("This is not a Windows executable.")
        }
        let offset = (0..<4).reduce(UInt32(0)) { $0 | UInt32(header[60 + $1]) << (8 * $1) }
        guard offset >= 64, offset <= 16_777_216 else { throw LibraryFailure.invalid("Invalid PE header.") }
        try handle.seek(toOffset: UInt64(offset))
        let signature = try handle.read(upToCount: 26) ?? Data()
        guard signature.count == 26, Array(signature.prefix(4)) == [0x50, 0x45, 0, 0] else {
            throw LibraryFailure.invalid("Invalid PE signature.")
        }
        return signature
    }

    static func machine(_ url: URL) throws -> UInt16 {
        let header = try peHeader(url)
        return UInt16(header[4]) | UInt16(header[5]) << 8
    }

    static func gameExecutableMachine(_ url: URL) throws -> UInt16 {
        let values = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
        guard url.pathExtension.lowercased() == "exe", values.isRegularFile == true,
              values.isSymbolicLink != true else {
            throw LibraryFailure.invalid("Select a Windows .exe game file, not game data, a folder, or a shortcut.")
        }
        let header = try peHeader(url)
        let characteristics = UInt16(header[22]) | UInt16(header[23]) << 8
        let optionalSize = UInt16(header[20]) | UInt16(header[21]) << 8
        let magic = UInt16(header[24]) | UInt16(header[25]) << 8
        guard characteristics & 0x0002 != 0, characteristics & 0x2000 == 0,
              optionalSize >= 2, magic == 0x010b || magic == 0x020b else {
            throw LibraryFailure.invalid("This file is not a Windows executable application. Renaming game data or a DLL to .exe does not make it playable.")
        }
        return UInt16(header[4]) | UInt16(header[5]) << 8
    }

    static func windowsPath(_ executable: URL, drive: URL) throws -> String {
        guard isInside(executable, root: drive) else { throw LibraryFailure.invalid("The executable must be inside this app's C: drive.") }
        let relative = String(executable.resolvingSymlinksInPath().path.dropFirst(drive.resolvingSymlinksInPath().path.count + 1))
        let path = "C:\\" + relative.replacingOccurrences(of: "/", with: "\\")
        guard path.utf8.count < 500 else { throw LibraryFailure.invalid("Move this game to a shorter folder path in C:\\Games.") }
        return path
    }

    static func discover(in directory: URL) throws -> [LibraryGame] {
        let root = directory.resolvingSymlinksInPath().standardizedFileURL
        let manager = FileManager.default
        try manager.createDirectory(at: root, withIntermediateDirectories: true)
        guard let enumerator = manager.enumerator(at: root, includingPropertiesForKeys: [.isSymbolicLinkKey, .isRegularFileKey], options: [.skipsHiddenFiles, .skipsPackageDescendants]) else { return [] }
        var games: [LibraryGame] = []
        for case let entry as URL in enumerator {
            let values = try entry.resourceValues(forKeys: [.isSymbolicLinkKey, .isRegularFileKey])
            if values.isSymbolicLink == true { enumerator.skipDescendants(); continue }
            let file = entry.resolvingSymlinksInPath().standardizedFileURL
            guard values.isRegularFile == true, file.pathExtension.lowercased() == "exe",
                  isInside(file, root: root), !isSupportPath(String(file.path.dropFirst(root.path.count + 1))) else { continue }
            guard (try? gameExecutableMachine(file)) != nil else { continue }
            let folder = file.deletingLastPathComponent()
            let metadataURL = folder.appendingPathComponent("somethingpc-game.json")
            let metadata = (try? Data(contentsOf: metadataURL)).flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: String] } ?? [:]
            let stem = file.deletingPathExtension().lastPathComponent
            let names = [metadata["cover"], "cover.png", "cover.jpg", "folder.jpg", "header.jpg", stem + ".png", stem + ".jpg"].compactMap { $0 }
            let cover = names.map { folder.appendingPathComponent($0) }.first {
                isInside($0, root: folder) && ["png", "jpg", "jpeg"].contains($0.pathExtension.lowercased()) && manager.fileExists(atPath: $0.path)
            }
            let rawID = metadata["steamAppID"] ?? (try? String(contentsOf: folder.appendingPathComponent("steam_appid.txt"), encoding: .utf8)) ?? ""
            let steamID = rawID.trimmingCharacters(in: .whitespacesAndNewlines)
            let validID = !steamID.isEmpty && steamID.count <= 10 && steamID.allSatisfy { $0.isASCII && $0.isNumber }
            let relative = String(file.path.dropFirst(root.path.count + 1))
            games.append(LibraryGame(id: relative, title: metadata["title"] ?? stem,
                publisher: metadata["publisher"] ?? folder.lastPathComponent,
                executable: file, cover: cover, steamID: validID ? steamID : nil))
        }
        let groups = Dictionary(grouping: games) { game -> String in
            let parts = game.id.split(separator: "/")
            return parts.count > 1 ? "folder:" + String(parts[0]) : game.id
        }
        return groups.map { id, entries in
            let sorted = entries.sorted {
                let leftDepth = $0.id.split(separator: "/").count
                let rightDepth = $1.id.split(separator: "/").count
                return leftDepth == rightDepth ? $0.id.localizedStandardCompare($1.id) == .orderedAscending : leftDepth < rightDepth
            }
            let first = sorted[0]
            let depth = first.id.split(separator: "/").count
            let preferred = sorted.filter { $0.id.split(separator: "/").count == depth }
            let selected = preferred.count == 1 ? first : nil
            let folder = id.hasPrefix("folder:") ? root.appendingPathComponent(String(id.dropFirst(7))) : root
            var game = LibraryGame(id: id, title: selected?.title ?? folder.lastPathComponent,
                publisher: selected?.publisher ?? "Choose launch executable",
                executable: selected?.executable, cover: selected?.cover ?? first.cover, steamID: selected?.steamID ?? first.steamID)
            game.candidates = sorted.compactMap(\.executable)
            game.folder = folder
            return game
        }.sorted { $0.title.localizedStandardCompare($1.title) == .orderedAscending }
    }

    static func copyImport(_ source: URL, to root: URL, folder: Bool) throws {
        let manager = FileManager.default
        let values = try source.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey])
        guard source.resolvingSymlinksInPath() != root.resolvingSymlinksInPath(), !isInside(root, root: source) else {
            throw LibraryFailure.invalid("Cannot import a folder into itself. Select the original game folder outside C:\\Games.")
        }
        guard values.isSymbolicLink != true, values.isDirectory == folder else { throw LibraryFailure.invalid("Choose a game folder or Windows EXE, not a shortcut.") }
        if !folder {
            guard source.pathExtension.lowercased() == "exe" else { throw LibraryFailure.invalid("Choose a Windows .exe file.") }
            _ = try gameExecutableMachine(source)
        }
        let staging = root.appendingPathComponent(".import-" + UUID().uuidString, isDirectory: true)
        try manager.createDirectory(at: staging, withIntermediateDirectories: true)
        defer { try? manager.removeItem(at: staging) }
        let payload = staging.appendingPathComponent(source.lastPathComponent)
        if folder {
            guard let files = manager.enumerator(at: source, includingPropertiesForKeys: [.isSymbolicLinkKey], options: []) else { throw LibraryFailure.invalid("Cannot read this folder.") }
            for case let file as URL in files {
                if try file.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink == true {
                    throw LibraryFailure.invalid("Game folders containing symbolic links cannot be imported. Copy the original files instead.")
                }
            }
        }
        try manager.copyItem(at: source, to: payload)
        let name = source.deletingPathExtension().lastPathComponent + "-" + UUID().uuidString.prefix(8)
        let destination = root.appendingPathComponent(String(name), isDirectory: true)
        if folder { try manager.moveItem(at: payload, to: destination) }
        else { try manager.moveItem(at: staging, to: destination) }
    }
}

enum StartupStage: Int, CaseIterable {
    case requested, jitReady, filesReady, runtimeReady, poolReady, serverReady, processReady, firstFrame
    var percent: Int { 1 + rawValue * 99 / (Self.allCases.count - 1) }
    var title: String {
        switch self {
        case .requested: return "Requesting JIT access"
        case .jitReady: return "Checking game files"
        case .filesReady: return "Preparing Windows runtime"
        case .runtimeReady: return "Allocating executable memory"
        case .poolReady: return "Starting Windows services"
        case .serverReady: return "Starting the application"
        case .processReady: return "Waiting for the first rendered frame"
        case .firstFrame: return "Ready"
        }
    }
}

enum RuntimeRegistry {
    static let key = "Software\\\\Microsoft\\\\VisualStudio\\\\14.0\\\\VC\\\\Runtimes\\\\arm64"

    static func section(in text: String) -> String {
        let header = "[" + key + "]"
        guard let range = text.range(of: "\n" + header).map({ text.index(after: $0.lowerBound)..<$0.upperBound }) ??
                (text.hasPrefix(header) ? text.startIndex..<text.index(text.startIndex, offsetBy: header.count) : nil) else { return "" }
        let end = text.range(of: "\n[", range: range.upperBound..<text.endIndex).map { text.index(after: $0.lowerBound) } ?? text.endIndex
        return String(text[range.lowerBound..<end])
    }

    static func replacing(in text: String, with replacement: String) -> String {
        let old = section(in: text)
        if old.isEmpty { return replacement.isEmpty ? text : text + "\n" + replacement }
        return text.replacingOccurrences(of: old, with: replacement)
    }
}
