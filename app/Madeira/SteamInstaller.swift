import Foundation
import SwiftUI

final class StoreTransferDelegate: NSObject, URLSessionDownloadDelegate {
    let limit: Int64
    let progress: @Sendable (Int64) -> Void
    init(limit: Int64, progress: @escaping @Sendable (Int64) -> Void) { self.limit = limit; self.progress = progress }
    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didFinishDownloadingTo location: URL) {}
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        let authenticated = task.originalRequest?.value(forHTTPHeaderField: "Authorization") != nil || task.originalRequest?.url?.path == "/token"
        completionHandler(request.url?.scheme == "https" && (!authenticated || request.url?.host == task.originalRequest?.url?.host) ? request : nil)
    }
    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didWriteData bytesWritten: Int64, totalBytesWritten: Int64, totalBytesExpectedToWrite: Int64) {
        if totalBytesWritten > limit || totalBytesExpectedToWrite > limit { downloadTask.cancel() }
        else { progress(totalBytesWritten) }
    }
}

enum StoreNetwork {
    private static let session = URLSession(configuration: .ephemeral)
    static func download(_ url: URL, token: String? = nil, limit: Int64, progress: @escaping @Sendable (Int64) -> Void = { _ in }) async throws -> URL {
        guard url.scheme == "https", url.user == nil, url.password == nil else { throw LibraryFailure.invalid("Store downloads require HTTPS.") }
        var request = URLRequest(url: url)
        request.timeoutInterval = 90
        request.setValue("SomethingPC/0.6", forHTTPHeaderField: "User-Agent")
        if let token {
            guard ["auth.gog.com", "embed.gog.com", "api.gog.com", "content-system.gog.com"].contains(url.host ?? "") else {
                throw LibraryFailure.invalid("Refused to send store credentials to an untrusted host.")
            }
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let delegate = StoreTransferDelegate(limit: limit, progress: progress)
        let (file, response) = try await session.download(for: request, delegate: delegate)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            try? FileManager.default.removeItem(at: file)
            throw LibraryFailure.invalid("Store request failed (HTTP \((response as? HTTPURLResponse)?.statusCode ?? 0)). Sign in again if authorization expired.")
        }
        guard let size = try file.resourceValues(forKeys: [.fileSizeKey]).fileSize, size <= limit else {
            try? FileManager.default.removeItem(at: file)
            throw LibraryFailure.invalid("Store response exceeded its size limit.")
        }
        return file
    }

    static func data(_ url: URL, token: String? = nil, limit: Int64 = 16_777_216) async throws -> Data {
        let file = try await download(url, token: token, limit: limit)
        defer { try? FileManager.default.removeItem(at: file) }
        return try Data(contentsOf: file)
    }

    static func json(_ url: URL, token: String? = nil) async throws -> [String: Any] {
        let data = try await data(url, token: token)
        guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { throw LibraryFailure.invalid("Invalid store response.") }
        return object
    }
}

@MainActor final class StoreInstallation: ObservableObject {
    static let shared = StoreInstallation()
    @Published private(set) var busy = false
    @Published private(set) var title = ""
    @Published private(set) var phase = ""
    @Published private(set) var completed: Int64 = 0
    @Published private(set) var total: Int64 = 0
    @Published private(set) var error: String?
    private var task: Task<Void, Never>?

    func start(_ title: String, operation: @escaping @Sendable () async throws -> Void) {
        guard !busy else { return }
        guard !LinuxVMSession.shared.started, !LinuxVMSession.shared.installing else {
            error = "Restart My-pc before installing Windows software after a Linux session."
            return
        }
        guard !GameLibrary.shared.sessionStarted, wine_process_is_running() == 0, wineserver_is_running() == 0 else {
            error = "Restart Something PC before installing. Files cannot be changed while Windows is running."
            return
        }
        busy = true
        error = nil
        self.title = title
        phase = "Preparing"
        completed = 0; total = 0
        task = Task {
            do {
                try await operation()
                phase = "Installed. Return to Library to play."
                GameLibrary.shared.refreshSteamClient()
                GameLibrary.shared.refresh()
            } catch is CancellationError { phase = "Cancelled. Verified download packages are kept for retry." }
            catch {
                if Task.isCancelled { phase = "Cancelled." }
                else { self.error = error.localizedDescription; phase = "Installation stopped. Retry when ready." }
            }
            busy = false
            task = nil
        }
    }

    func update(_ phase: String, completed: Int64 = 0, total: Int64 = 0) {
        guard busy else { return }
        self.phase = phase; self.completed = completed; self.total = total
    }
    func cancel() { task?.cancel() }
}

enum SteamInstaller {
    static let directory = GameLibrary.drive.appendingPathComponent("Steam")
    static var installedClients: [SteamClientInstallation] {
        SteamClientInstallation.findAll(in: GameLibrary.drive)
    }
    static var isInstalled: Bool { !installedClients.isEmpty }
    static var libraryDirectories: [URL] {
        [directory] + installedClients.map(\.directory).filter { $0.standardizedFileURL != directory.standardizedFileURL }
    }

    static func gameLaunch(containing executable: URL) throws -> (app: SteamInstalledApp, directory: URL)? {
        for root in libraryDirectories {
            guard GameFiles.isInside(executable, root: root.appendingPathComponent("steamapps/common")) else { continue }
            if let app = try SteamLibraryCatalog(steamDirectory: root).app(containing: executable) {
                return (app, root)
            }
        }
        return nil
    }

    static func install() async throws {
        let manager = FileManager.default
        let cache = manager.urls(for: .cachesDirectory, in: .userDomainMask)[0].resolvingSymlinksInPath().appendingPathComponent("SteamPackages")
        try manager.createDirectory(at: cache, withIntermediateDirectories: true)
        let data = try await StoreNetwork.data(URL(string: "https://client-update.fastly.steamstatic.com/steam_client_win64")!, limit: 2_000_000)
        guard let text = String(data: data, encoding: .utf8) else { throw LibraryFailure.invalid("Invalid Valve manifest encoding.") }
        let manifest = try ValveManifest(text)
        let total = manifest.packages.reduce(Int64(0)) { $0 + $1.size }
        try StoreFiles.requireSpace(max(total * 5, 2_147_483_648), at: cache)
        let staging = cache.appendingPathComponent("staging-\(UUID().uuidString)")
        try manager.createDirectory(at: staging, withIntermediateDirectories: true)
        defer { try? manager.removeItem(at: staging) }
        var complete: Int64 = 0
        for package in manifest.packages {
            try Task.checkCancellation()
            let file = try StoreFiles.destination(package.file, root: cache)
            if (try? StoreFiles.digest(file)) != package.sha256 {
                let baseline = complete
                let downloaded = try await StoreNetwork.download(URL(string: "https://client-update.fastly.steamstatic.com/\(package.file)")!, limit: package.size) { bytes in
                    Task { @MainActor in StoreInstallation.shared.update("Downloading \(package.name)", completed: baseline + bytes, total: total) }
                }
                defer { try? manager.removeItem(at: downloaded) }
                guard try downloaded.resourceValues(forKeys: [.fileSizeKey]).fileSize.map(Int64.init) == package.size,
                      try StoreFiles.digest(downloaded) == package.sha256 else {
                    throw LibraryFailure.invalid("Valve package checksum mismatch: \(package.name). Nothing from that package was installed.")
                }
                if manager.fileExists(atPath: file.path) { try manager.removeItem(at: file) }
                try manager.moveItem(at: downloaded, to: file)
            }
            complete += package.size
            await StoreInstallation.shared.update("Extracting \(package.name)", completed: complete, total: total)
            try StoreZIP.extract(file, to: staging)
        }
        guard try GameFiles.gameExecutableMachine(staging.appendingPathComponent("steam.exe")) == 0x8664 else {
            throw LibraryFailure.invalid("Valve's package did not contain the 64-bit Steam client.")
        }
        try Task.checkCancellation()
        await StoreInstallation.shared.update("Installing verified Steam client", completed: total, total: total)
        try commit(staging, version: manifest.version)
    }

    private static func commit(_ staging: URL, version: String) throws {
        let manager = FileManager.default
        madeira_seed_prefix_if_needed(GameLibrary.documents.appendingPathComponent("wine").path)
        _ = try StoreFiles.destination("Steam", root: GameLibrary.drive)
        try manager.createDirectory(at: directory, withIntermediateDirectories: true)
        let marker = try StoreFiles.destination(".somethingpc-installing", root: directory)
        try Data(version.utf8).write(to: marker, options: .atomic)
        guard let enumerator = manager.enumerator(at: staging, includingPropertiesForKeys: [.isDirectoryKey, .isRegularFileKey]) else { throw LibraryFailure.invalid("Cannot enumerate Steam installation.") }
        for case let file as URL in enumerator {
            try Task.checkCancellation()
            let relative = String(file.path.dropFirst(staging.path.count + 1))
            guard !["steamapps", "userdata", "config"].contains(relative.split(separator: "/").first?.lowercased() ?? "") else {
                enumerator.skipDescendants()
                continue
            }
            let target = try StoreFiles.destination(relative, root: directory)
            let values = try file.resourceValues(forKeys: [.isDirectoryKey, .isRegularFileKey])
            if values.isDirectory == true { try manager.createDirectory(at: target, withIntermediateDirectories: true) }
            else if values.isRegularFile == true {
                try manager.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
                if manager.fileExists(atPath: target.path) { _ = try manager.replaceItemAt(target, withItemAt: file) }
                else { try manager.moveItem(at: file, to: target) }
            } else { throw LibraryFailure.invalid("Unexpected Steam package file type.") }
        }
        try Data(version.utf8).write(to: directory.appendingPathComponent(".somethingpc-version"), options: .atomic)
        try manager.removeItem(at: marker)
        SessionDiagnostics.shared.event("Installed verified official Steam win64 packages; version \(version)")
    }

    static func prepareLaunch(appID: String? = nil, clientDirectory: URL? = nil) throws {
        let client = installedClients.first { clientDirectory == nil || $0.directory.standardizedFileURL == clientDirectory?.standardizedFileURL }
        guard let client else { throw LibraryFailure.invalid("Install or repair the complete 64-bit Steam client in Settings → Steam & GOG first. A downloaded SteamSetup.exe alone is not an installed client.") }
        guard jit_check_debugged() else { throw LibraryFailure.invalid("Steam requires FEX JIT. Enable JIT with StikDebug and retry.") }
        let defaults = UserDefaults.standard
        let interface = SteamInterface(rawValue: defaults.string(forKey: SteamLaunchPlan.interfaceKey) ?? "") ?? .standard
        let webEngine = SteamWebEngine(rawValue: defaults.string(forKey: SteamLaunchPlan.webEngineKey) ?? "") ?? .compatibility
        let plan = try SteamLaunchPlan(
            width: getenv("MADEIRA_SCREEN_W").flatMap { Int(String(cString: $0)) } ?? 960,
            height: getenv("MADEIRA_SCREEN_H").flatMap { Int(String(cString: $0)) } ?? 540,
            interface: interface, webEngine: webEngine, appID: appID, windowsDirectory: client.windowsDirectory)
        let file = try StoreFiles.destination("steam-launch.bat", root: GameLibrary.drive)
        try plan.batch.write(to: file, atomically: true, encoding: .utf8)
        for (key, value) in plan.environment { setenv(key, value, 1) }
        SessionDiagnostics.shared.event("Steam launch: ARM64 desktop → x64 Steam via FEX CPU JIT; web engine=\(webEngine.rawValue); interface=\(interface.rawValue); app=\(appID ?? "client")")
    }
}
