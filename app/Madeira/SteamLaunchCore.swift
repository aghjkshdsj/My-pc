import Foundation

enum SteamInterface: String, CaseIterable {
    case standard, bigPicture
    var title: String { self == .standard ? "Standard Steam" : "Big Picture (experimental)" }
}

enum SteamWebEngine: String, CaseIterable {
    case compatibility, jit
    var title: String { self == .compatibility ? "Compatibility" : "Web UI JIT (experimental)" }
}

/// FEX CPU translation always uses JIT. This switch affects only Chromium's V8 engine.
struct SteamLaunchPlan {
    static let interfaceKey = "steam.interface"
    static let webEngineKey = "steam.webEngine"
    let batch: String
    let environment: [String: String]

    init(width: Int, height: Int, interface: SteamInterface = .standard,
         webEngine: SteamWebEngine = .compatibility, appID: String? = nil) throws {
        guard (640...3840).contains(width), (360...2160).contains(height) else {
            throw LibraryFailure.invalid("Unsupported Steam desktop resolution.")
        }
        if let appID, !SteamInstalledApp.validID(appID) {
            throw LibraryFailure.invalid("Invalid Steam app ID.")
        }
        var arguments = "-no-cef-sandbox -cef-disable-gpu -nocrashmonitor -cef-disable-features=SegmentationPlatform,OptimizationTargetPrediction,OptimizationHints"
        if interface == .bigPicture { arguments += " -gamepadui" }
        if let appID { arguments += " -applaunch \(appID)" }
        batch = [
            "@echo off",
            "start \"\" \"C:\\windows\\system32\\services.exe\"",
            "cd /d \"C:\\Steam\"",
            "\"C:\\Steam\\steam.exe\" \(arguments)",
            ""
        ].joined(separator: "\r\n")
        environment = [
            "MADEIRA_USE_ARM64EC": "0", // Native desktop; x64 children enter ARM64EC/FEX.
            "MADEIRA_EXE": "explorer.exe",
            "MADEIRA_DESKTOP": "1",
            "MADEIRA_JITLESS": webEngine == .compatibility ? "1" : "0",
            "MADEIRA_ARGS": "/desktop=shell,\(width)x\(height) cmd /c C:\\steam-launch.bat"
        ]
    }

    static func route(app: SteamInstalledApp?, preference: Bool?, arguments: String) throws -> String? {
        guard preference != false else { return nil }
        guard let app else {
            if preference == true {
                throw LibraryFailure.invalid("Steam launch needs a matching installed appmanifest in C:\\Steam\\steamapps. Install the game through Steam, or choose Direct EXE in Game Settings.")
            }
            return nil
        }
        guard arguments.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw LibraryFailure.invalid("For Steam launches, set game arguments in Steam → Properties → Launch Options, or choose Direct EXE in Game Settings.")
        }
        return app.id
    }
}

struct SteamInstalledApp: Equatable {
    let id: String
    let name: String
    let directory: String

    static func validID(_ value: String) -> Bool {
        guard !value.isEmpty, value.count <= 10,
              value.allSatisfy({ $0.isASCII && $0.isNumber }),
              let number = UInt32(value), number > 0 else { return false }
        return String(number) == value
    }

    init(manifest: String, fileName: String) throws {
        guard manifest.utf8.count <= 1_048_576 else { throw LibraryFailure.invalid("Steam appmanifest is too large.") }
        var parser = ValveParser(characters: Array(manifest))
        let values = try parser.object(nested: false, depth: 0)
        guard let app = values["AppState"]?.object,
              let id = app["appid"]?.text, Self.validID(id),
              fileName == "appmanifest_\(id).acf",
              let directory = app["installdir"]?.text, !directory.isEmpty,
              directory != ".", directory != "..", directory.utf8.count <= 255,
              !directory.contains(where: { "/\\:".contains($0) || $0.asciiValue.map({ $0 < 32 }) == true }),
              let flagText = app["StateFlags"]?.text, let flags = UInt32(flagText), flags & 4 != 0 else {
            throw LibraryFailure.invalid("Invalid or incomplete Steam installation manifest.")
        }
        self.id = id
        self.directory = directory
        let name = app["name"]?.text ?? ""
        self.name = name.isEmpty ? directory : name
    }
}

/// Read only local Steam manifests. steam_appid.txt/artwork metadata is not launch authority.
struct SteamLibraryCatalog {
    let common: URL
    private let byFolder: [String: SteamInstalledApp]

    init(steamDirectory: URL) throws {
        let apps = try StoreFiles.destination("steamapps", root: steamDirectory)
        common = try StoreFiles.destination("steamapps/common", root: steamDirectory)
        let manager = FileManager.default
        guard manager.fileExists(atPath: apps.path) else { byFolder = [:]; return }
        let files = try manager.contentsOfDirectory(at: apps, includingPropertiesForKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
        guard files.count <= 20_000 else { throw LibraryFailure.invalid("Too many Steam manifest files.") }
        var entries: [String: SteamInstalledApp] = [:]
        var ambiguous = Set<String>()
        for file in files where file.lastPathComponent.hasPrefix("appmanifest_") && file.pathExtension == "acf" {
            guard let values = try? file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey]),
                  values.isRegularFile == true, values.isSymbolicLink != true,
                  let size = values.fileSize, size <= 1_048_576,
                  let text = try? String(contentsOf: file, encoding: .utf8),
                  let app = try? SteamInstalledApp(manifest: text, fileName: file.lastPathComponent) else { continue }
            let key = app.directory.lowercased()
            if entries[key] != nil { ambiguous.insert(key) }
            entries[key] = app
        }
        for key in ambiguous { entries.removeValue(forKey: key) }
        byFolder = entries
    }

    func app(containing file: URL) -> SteamInstalledApp? {
        guard GameFiles.isInside(file, root: common) else { return nil }
        let relative = String(file.resolvingSymlinksInPath().path.dropFirst(common.resolvingSymlinksInPath().path.count + 1))
        guard let folder = relative.split(separator: "/").first else { return nil }
        return byFolder[String(folder).lowercased()]
    }
}
