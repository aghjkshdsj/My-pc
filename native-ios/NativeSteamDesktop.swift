// SPDX-License-Identifier: GPL-3.0-or-later
// My-pc desktop Steam setup. Valve binaries are downloaded, never bundled.
import Foundation

enum NativeSteamDesktopFiles {
    static let origin = "https://client-update.fastly.steamstatic.com/"
    static let relativeRoot = "SteamDesktop"
    static let windowsRoot = "C:\\SteamDesktop"
    static let marker = ".mypc-desktop-steam.json"
    struct Manifest: Sendable {
        let version: Int
        let packages: [SteamRuntimeFiles.Package]
        var bytes: Int { packages.reduce(0) { $0 + $1.bytes } }
    }
    static func fail(_ reason: String) -> SteamFileError { .invalid(reason) }

    // Read only the main win64 distribution, not nested China/legacy variants.
    static func manifest(_ data: Data) throws -> Manifest {
        var reader = try SteamKeyValues(data)
        let value = try reader.read()
        guard let root = value["win64"], let version = root["version"]?.string.flatMap(Int.init), version > 0 else {
            throw fail("Valve's desktop Steam manifest is invalid.")
        }
        var packages: [SteamRuntimeFiles.Package] = [], keys = Set<String>(), files = Set<String>()
        let allowed = Set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-".utf8)
        for (key, node) in root.fields.sorted(by: { $0.key < $1.key }) where !node.fields.isEmpty {
            guard let name = node["file"]?.string, let size = node["size"]?.string.flatMap(Int.init),
                  let hash = node["sha2"]?.string?.lowercased(), (1...256 * 1024 * 1024).contains(size),
                  name.utf8.count < 160, !name.hasPrefix("."), name.contains(".zip."),
                  name.utf8.allSatisfy({ allowed.contains($0) }), files.insert(name.lowercased()).inserted,
                  hash.count == 64, hash.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else {
                throw fail("Valve's desktop Steam package metadata is invalid.")
            }
            keys.insert(key); packages.append(.init(file: name, bytes: size, sha256: hash))
        }
        let result = Manifest(version: version, packages: packages)
        guard (4...64).contains(packages.count), result.bytes <= 1024 * 1024 * 1024,
              Set(["steam_win64", "bins_win64", "bins_cef_win64", "bins_webhelpers_win64"]).isSubset(of: keys) else {
            throw fail("Valve's desktop Steam download is incomplete or too large.")
        }
        return result
    }

    static func isAMD64(_ data: Data) -> Bool {
        guard data.count >= 64, data[0] == 0x4d, data[1] == 0x5a else { return false }
        let pe = Int(data[60]) | Int(data[61]) << 8 | Int(data[62]) << 16 | Int(data[63]) << 24
        guard pe >= 64, pe <= data.count - 6 else { return false }
        return data.subdata(in: pe..<pe + 4) == Data([0x50, 0x45, 0, 0]) && data[pe + 4] == 0x64 && data[pe + 5] == 0x86
    }

    static func ready(drive: URL) -> Bool {
        let fm = FileManager.default
        guard let root = try? SteamRuntimeFiles.destination(relativeRoot, under: drive),
              fm.fileExists(atPath: root.appendingPathComponent(marker).path) else { return false }
        for name in ["steam.exe", "bin/cef/cef.win64/steamwebhelper.exe", "bin/cef/cef.win64/libcef.dll"] {
            guard let file = try? SteamRuntimeFiles.destination(relativeRoot + "/" + name, under: drive),
                  let values = try? file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey]),
                  values.isRegularFile == true, values.isSymbolicLink != true,
                  let data = try? Data(contentsOf: file, options: .mappedIfSafe), isAMD64(data) else { return false }
        }
        return true
    }

    static let batch = """
    @echo off\r
    rem My-pc desktop Steam. Sign in in Steam's own window.\r
    start "" "C:\\windows\\system32\\services.exe"\r
    cd /d "C:\\SteamDesktop"\r
    "C:\\SteamDesktop\\steam.exe" -no-cef-sandbox -cef-disable-gpu -console -nocrashmonitor -cef-disable-features=SegmentationPlatform,OptimizationTargetPrediction,OptimizationHints\r
    """

    // Register the existing native download folder as a second desktop library.
    // No account credentials or ownership claims are written into these files.
    static func libraryFolders(drive: URL) throws -> String {
        var apps: [String] = []
        let folder = try SteamRuntimeFiles.destination(SteamInstallPaths.libraryRelative, under: drive)
        if FileManager.default.fileExists(atPath: folder.path) {
            for name in try FileManager.default.contentsOfDirectory(atPath: folder.path).sorted().prefix(10000) {
                guard name.hasPrefix("appmanifest_"), name.hasSuffix(".acf"),
                      let id = Int(name.dropFirst(12).dropLast(4)), id > 0 else { continue }
                let size = SteamInstallFiles.sizeOnDisk(appID: id, steamApps: folder) ?? 0
                apps.append("\"\(id)\" \"\(max(0, size))\"")
            }
        }
        return "\"libraryfolders\" { \"0\" { \"path\" \"C:\\\\SteamDesktop\" \"apps\" {} } \"1\" { \"path\" \"C:\\\\Program Files (x86)\\\\Steam\" \"apps\" { \(apps.joined(separator: " ")) } } }\n"
    }

    // A full Steam session can change discovery keys. Restore only values that
    // name our dedicated desktop client before starting the pinned Dock helper.
    static func registryForLibrary(_ text: String, machine: Bool) throws -> String {
        var lines = text.components(separatedBy: "\n"), section = ""
        let headers = Set(["[software\\\\valve\\\\steam]", "[software\\\\wow6432node\\\\valve\\\\steam]", "[software\\\\valve\\\\steam\\\\activeprocess]"])
        let names = Set(["installpath", "steampath", "steamexe", "steamclientdll", "steamclientdll64"])
        for index in lines.indices {
            let line = lines[index]
            if line.hasPrefix("["), let end = line.firstIndex(of: "]") { section = String(line[...end]).lowercased() }
            guard headers.contains(section), let equals = line.firstIndex(of: "="), line.hasPrefix("\"") else { continue }
            let name = String(line[..<equals]).trimmingCharacters(in: CharacterSet(charactersIn: "\"")).lowercased()
            let old = String(line[line.index(after: equals)...])
            guard names.contains(name), old.lowercased().hasPrefix("\"c:\\\\steamdesktop") else { continue }
            let tail = String(old.dropFirst("\"C:\\\\SteamDesktop".count))
            guard tail == "\"" || tail.hasPrefix("\\\\") else { continue }
            lines[index] = String(line[..<equals]) + "=\"" + SteamRuntimeFiles.windowsRoot.replacingOccurrences(of: "\\", with: "\\\\") + tail
        }
        return try SteamRuntimeFiles.registry(lines.joined(separator: "\n"), machine: machine)
    }
}

#if canImport(UIKit) && canImport(CryptoKit)
import CryptoKit

private final class NativeSteamDesktopRedirects: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        let url = request.url
        completionHandler(url?.scheme == "https" && url?.host == "client-update.fastly.steamstatic.com"
            && (url?.port == nil || url?.port == 443) && url?.user == nil && url?.password == nil ? request : nil)
    }
}

actor NativeSteamDesktopInstaller {
    static let shared = NativeSteamDesktopInstaller()
    private var busy = false

    func prepare(prefix: URL, progress: @Sendable (String) async -> Void) async throws {
        guard !busy, wine_process_is_running() == 0, wineserver_is_running() == 0 else { throw SteamRuntimeFiles.Failure.activeSession }
        busy = true; defer { busy = false }
        let fm = FileManager.default, drive = prefix.appendingPathComponent("drive_c")
        if NativeSteamDesktopFiles.ready(drive: drive) { return }
        let root = try SteamRuntimeFiles.destination(NativeSteamDesktopFiles.relativeRoot, under: drive)
        guard !fm.fileExists(atPath: root.path) else { throw NativeSteamDesktopFiles.fail("The desktop Steam installation is incomplete. Its files were kept; check SteamDesktop in the app's Files folder.") }
        if !fm.fileExists(atPath: prefix.appendingPathComponent(".update-timestamp").path),
           ["system.reg", "user.reg"].contains(where: { fm.fileExists(atPath: prefix.appendingPathComponent($0).path) }) {
            throw SteamRuntimeFiles.Failure.conflict
        }
        // Stage beside the final directory so one rename publishes the entire
        // client. Cancellation, bad hashes and ZIP errors leave it uninstalled.
        try fm.createDirectory(at: drive, withIntermediateDirectories: true)
        let stage = try SteamRuntimeFiles.destination(".mypc-steam-stage-" + UUID().uuidString, under: drive)
        try fm.createDirectory(at: stage, withIntermediateDirectories: false)
        defer { try? fm.removeItem(at: stage) }
        let config = URLSessionConfiguration.ephemeral
        config.httpCookieStorage = nil; config.urlCredentialStorage = nil
        config.timeoutIntervalForRequest = 60; config.timeoutIntervalForResource = 1200
        let session = URLSession(configuration: config, delegate: NativeSteamDesktopRedirects(), delegateQueue: nil)
        defer { session.invalidateAndCancel() }
        await progress("Checking Valve's desktop Steam download…")
        let manifestURL = URL(string: NativeSteamDesktopFiles.origin + "steam_client_win64")!
        let (manifestTemp, manifestResponse) = try await session.download(from: manifestURL)
        defer { try? fm.removeItem(at: manifestTemp) }
        try Self.check(manifestResponse, url: manifestURL)
        guard ((try manifestTemp.resourceValues(forKeys: [.fileSizeKey])).fileSize ?? Int.max) <= 4 * 1024 * 1024 else { throw SteamRuntimeFiles.Failure.invalidPackage }
        let manifest = try NativeSteamDesktopFiles.manifest(Data(contentsOf: manifestTemp))
        let space = try drive.resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey]).volumeAvailableCapacityForImportantUsage
        if let space, space < Int64(manifest.bytes + 2 * 1024 * 1024 * 1024) { throw NativeSteamDesktopFiles.fail("Desktop Steam setup needs at least 3 GB of free space. Free some space and try again.") }
        var completed = 0, names = Set<String>(), expanded = 0
        for (index, package) in manifest.packages.enumerated() {
            try Task.checkCancellation()
            await progress("Downloading desktop Steam (\(index + 1)/\(manifest.packages.count), \(completed / 1048576)/\(manifest.bytes / 1048576) MB)…")
            let url = URL(string: NativeSteamDesktopFiles.origin + package.file)!
            let (temp, response) = try await session.download(from: url)
            defer { try? fm.removeItem(at: temp) }
            try Self.check(response, url: url)
            guard (try temp.resourceValues(forKeys: [.fileSizeKey])).fileSize == package.bytes else { throw SteamRuntimeFiles.Failure.invalidPackage }
            let archive = try Data(contentsOf: temp, options: .mappedIfSafe)
            guard SHA256.hash(data: archive).map({ String(format: "%02x", $0) }).joined() == package.sha256 else { throw SteamRuntimeFiles.Failure.invalidPackage }
            await progress("Verifying and unpacking desktop Steam (\(index + 1)/\(manifest.packages.count))…")
            try SteamRuntimeFiles.unpack(archive, desktop: true) { name, bytes in
                expanded += bytes.count
                guard expanded <= 2 * 1024 * 1024 * 1024 else { throw SteamRuntimeFiles.Failure.invalidPackage }
                let file = try SteamRuntimeFiles.destination(name, under: stage)
                // Some client distributions repeat identical shared files.
                if !names.insert(name.lowercased()).inserted {
                    guard fm.fileExists(atPath: file.path), try Data(contentsOf: file, options: .mappedIfSafe) == bytes else { throw SteamRuntimeFiles.Failure.invalidPackage }
                    return
                }
                try fm.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
                try bytes.write(to: file, options: .atomic)
            }
            completed += package.bytes
        }
        let metadata: [String: Any] = ["schema": 1, "valve_version": manifest.version, "distribution": "win64", "download_bytes": manifest.bytes]
        try JSONSerialization.data(withJSONObject: metadata, options: [.sortedKeys]).write(to: stage.appendingPathComponent(NativeSteamDesktopFiles.marker), options: .atomic)
        // Validate all required x64 programs before touching the prefix seed.
        for name in ["steam.exe", "bin/cef/cef.win64/steamwebhelper.exe", "bin/cef/cef.win64/libcef.dll"] {
            guard NativeSteamDesktopFiles.isAMD64(try Data(contentsOf: stage.appendingPathComponent(name), options: .mappedIfSafe)) else { throw SteamRuntimeFiles.Failure.invalidPackage }
        }
        try Task.checkCancellation()
        guard wine_process_is_running() == 0, wineserver_is_running() == 0 else { throw SteamRuntimeFiles.Failure.activeSession }
        await progress("Finishing desktop Steam setup…")
        try Task.checkCancellation()
        guard wine_process_is_running() == 0, wineserver_is_running() == 0 else { throw SteamRuntimeFiles.Failure.activeSession }
        madeira_seed_prefix_if_needed(prefix.path)
        guard ["system.reg", "user.reg"].allSatisfy({ fm.fileExists(atPath: prefix.appendingPathComponent($0).path) }), !fm.fileExists(atPath: root.path) else { throw SteamRuntimeFiles.Failure.prefixMissing }
        try fm.moveItem(at: stage, to: root)
    }

    private static func check(_ response: URLResponse, url: URL) throws {
        guard let http = response as? HTTPURLResponse, http.statusCode == 200, http.url == url else { throw SteamRuntimeFiles.Failure.invalidPackage }
    }
}

enum NativeSteamDesktopLaunch {
    static func prepare(prefix: URL) throws {
        guard wine_process_is_running() == 0, wineserver_is_running() == 0 else { throw SteamRuntimeFiles.Failure.activeSession }
        let fm = FileManager.default, drive = prefix.appendingPathComponent("drive_c")
        guard NativeSteamDesktopFiles.ready(drive: drive) else { throw NativeSteamDesktopFiles.fail("Download desktop Steam before launching it.") }
        let apps = try SteamRuntimeFiles.destination("SteamDesktop/steamapps", under: drive)
        try fm.createDirectory(at: apps, withIntermediateDirectories: true)
        // Keep any libraries the owner added in Steam; create this only once.
        let folders = try SteamRuntimeFiles.destination("SteamDesktop/steamapps/libraryfolders.vdf", under: drive)
        if !fm.fileExists(atPath: folders.path) {
            try NativeSteamDesktopFiles.libraryFolders(drive: drive).write(to: folders, atomically: true, encoding: .utf8)
        }
        let batch = try SteamRuntimeFiles.destination("mypc-steam-desktop.bat", under: drive)
        try NativeSteamDesktopFiles.batch.write(to: batch, atomically: true, encoding: .utf8)
    }
    static func restoreLibraryDiscovery(prefix: URL) throws {
        guard wine_process_is_running() == 0, wineserver_is_running() == 0 else { throw SteamRuntimeFiles.Failure.activeSession }
        let drive = prefix.appendingPathComponent("drive_c")
        guard NativeSteamDesktopFiles.ready(drive: drive) else { return }
        var pending: [(URL, Data)] = []
        for (name, machine) in [("system.reg", true), ("user.reg", false)] {
            let url = prefix.appendingPathComponent(name)
            guard url.standardizedFileURL.path == url.resolvingSymlinksInPath().standardizedFileURL.path else { throw SteamRuntimeFiles.Failure.conflict }
            let old = try String(contentsOf: url, encoding: .utf8)
            let new = try NativeSteamDesktopFiles.registryForLibrary(old, machine: machine)
            if new != old { pending.append((url, Data(new.utf8))) }
        }
        for (url, data) in pending { try data.write(to: url, options: .atomic) }
    }
}
#endif
